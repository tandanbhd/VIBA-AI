# -*- coding: utf-8 -*-

# === Nhập các thư viện cần thiết ===
from flask import Flask, request, jsonify, render_template #Framework web chính, xử lý route, request, response, render
from googleapiclient.discovery import build # Thư viện Google API Client
from googleapiclient.errors import HttpError # Thư viện Google API Client
from docx import Document # Thư viện để đọc file Word
from flask_cors import CORS # Cho phép gọi API từ frontend (JS trong index.html)
import google.generativeai as genai # Thư viện Google Gemini AI
import io # Xử lý dữ liệu file Word dạng byte từ Google Drive trả về
from google.oauth2 import service_account # Thư viện để xác thực Google API
import csv # Thư viện để đọc file CSV
import os # Thư viện để xử lý biến môi trường (GOOGLE_API_KEY, GOOGLE_SHEET_ID, ADMIN_PASSWORD, v.v.)
import json # Parse nội dung JSON từ biến môi trường (Service Account JSON)
import openpyxl # Thư viện để đọc file Excel
from datetime import datetime # Thêm thư viện datetime để lấy giờ Việt Nam  
import pytz # Đảm bảo thời gian ghi log theo đúng múi giờ Việt Nam (Asia/Ho_Chi_Minh)

""" Deploy: Bỏ dotenv nếu chạy trên Render, vì biến môi trường đã được thiết lập trên Render"""
#from dotenv import load_dotenv # Thư viện để đọc biến môi trường từ file .env (nếu chạy local)
#load_dotenv()  # Tự động đọc từ .env nếu chạy local


CHAT_SESSIONS = {}  # Dict: ma_can_bo -> phiên chat riêng


# Thêm các thư viện để tạo logchat
from flask import request, render_template, redirect, url_for 
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') # Lấy mật khẩu admin từ biến môi trường xem logchat
from datetime import datetime
from googleapiclient.discovery import build as build_sheet
from googleapiclient.errors import HttpError as SheetHttpError
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')  # Biến google Sheet ID từ biến môi trường
SHEET_SERVICE = None
EMPLOYEE_NAME_MAP = {}  # ma_can_bo -> ho_ten

# === Khởi tạo ứng dụng Flask ===
app = Flask(__name__)
CORS(app)

# === Cấu hình API ===

# --- Cấu hình Gemini API ---
# Lấy API Key từ biến môi trường
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    print("LỖI: Biến môi trường GOOGLE_API_KEY chưa được thiết lập.")
    # Thoát hoặc xử lý lỗi phù hợp ở đây
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print("Đã cấu hình Gemini API thành công.")
    except Exception as e:
        print(f"LỖI CẤU HÌNH GEMINI API: {e}. Vui lòng kiểm tra API Key.")

MODEL_NAME = "gemini-2.5-flash" # Hoặc model bạn muốn dùng
generation_config = {
    "max_output_tokens": 1024,
    "temperature": 0.6,
    "top_p": 1.0
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# --- Cấu hình Google Drive API ---
DRIVE_SERVICE = None
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Lấy nội dung Service Account JSON từ biến môi trường
SERVICE_ACCOUNT_INFO_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
# Lấy Folder ID từ biến môi trường
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')

if not SERVICE_ACCOUNT_INFO_JSON:
    print("LỖI: Biến môi trường GOOGLE_SERVICE_ACCOUNT_JSON chưa được thiết lập.")
if not DRIVE_FOLDER_ID:
     print("LỖI: Biến môi trường DRIVE_FOLDER_ID chưa được thiết lập.")

# --- Cấu hình File dữ liệu cán bộ ---
# Tên file vẫn giữ nguyên, file này cần được đưa lên repo GitHub cùng code
EMPLOYEE_DATA_FILE = 'can_bo.csv'

# === Biến toàn cục lưu trữ dữ liệu ===
WORD_FILES = {}
WORD_CONTENTS = {}
EXCEL_FILES = {}
EXCEL_CONTENTS = {}
CHAT_SESSIONS = {}  # Dict: ma_can_bo -> phiên chat riêng
hungdaica = """
VIBA là một ứng dụng AI được phát triển bởi Nguyễn Thái Hùng, nhằm hỗ trợ cán bộ BIDV Bắc Hải Dương trong việc tra cứu thông tin và giải đáp thắc mắc dựa trên tài liệu đã cung cấp.
Ứng dụng này sử dụng công nghệ AI tiên tiến để cung cấp câu trả lời chính xác và nhanh chóng cho các câu hỏi liên quan đến tài liệu, giúp tiết kiệm thời gian và nâng cao hiệu quả công việc của cán bộ ngân hàng.
Với VIBA, cán bộ có thể dễ dàng tra cứu thông tin về các sản phẩm, dịch vụ, quy trình làm việc và các vấn đề liên quan đến ngân hàng mà không cần phải tìm kiếm trong tài liệu thủ công.
Ứng dụng này được thiết kế để hỗ trợ cán bộ trong việc nâng cao kiến thức và kỹ năng, từ đó cải thiện chất lượng dịch vụ khách hàng và tăng cường sự hài lòng của khách hàng đối với ngân hàng.
VIBA là viết tắt của 'Virtual Intelligent BIDV Bắc Hải Dương Assistant'.
Ứng dụng này do Nguyễn Thái Hùng - Giám đốc PGD Tân Dân - BIDV Bắc Hải Dương phát triển.
Trong tương lai, VIBA sẽ tiếp tục được cải tiến và nâng cấp để đáp ứng tốt hơn nhu cầu của cán bộ ngân hàng và khách hàng.
Với sự phát triển không ngừng của công nghệ AI, VIBA sẽ trở thành một công cụ hữu ích và cần thiết cho cán bộ ngân hàng trong việc nâng cao chất lượng dịch vụ và cải thiện trải nghiệm của khách hàng.
Trong quá trình sử dụng, nếu cán bộ có bất kỳ câu hỏi nào về ứng dụng hoặc cần hỗ trợ, vui lòng liên hệ với Nguyễn Thái Hùng để được hỗ trợ.
"""

# === Các hàm hỗ trợ ===

def setup_drive_service():
    """Thiết lập kết nối đến Google Drive API sử dụng Service Account từ biến môi trường."""
    global DRIVE_SERVICE
    if not SERVICE_ACCOUNT_INFO_JSON:
         print("(!) Bỏ qua thiết lập Drive: Biến môi trường Service Account JSON chưa có.")
         DRIVE_SERVICE = None
         return

    try:
        # Parse chuỗi JSON từ biến môi trường thành dictionary
        service_account_info = json.loads(SERVICE_ACCOUNT_INFO_JSON)
        # Tạo thông tin xác thực từ dictionary
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES)
        # Xây dựng đối tượng dịch vụ Drive
        DRIVE_SERVICE = build('drive', 'v3', credentials=creds)
    except json.JSONDecodeError:
        print(f"LỖI: Không thể parse Service Account JSON từ biến môi trường. Google Drive sẽ không được sử dụng.")
        DRIVE_SERVICE = None
    except Exception as e:
        print(f"LỖI khi thiết lập kết nối Google Drive: {e}")
        DRIVE_SERVICE = None

# Các hàm xử lý file Word
def get_all_word_files(folder_id):
    """Lấy danh sách tên và ID các file Word (.docx) trong thư mục Google Drive chỉ định."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE:
        print("(!) Bỏ qua lấy file Word: Kết nối Google Drive chưa được thiết lập.")
        return {} # Trả về dict rỗng nếu không có kết nối
    if not folder_id:
         print("(!) Bỏ qua lấy file Word: DRIVE_FOLDER_ID chưa được thiết lập.")
         return {}

    files_found = {}
    page_token = None
    print(f"-> Bắt đầu tìm file Word trong thư mục Drive ID: {folder_id}...")
    try:
        while True:
            response = DRIVE_SERVICE.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageToken=page_token
            ).execute()
            files = response.get('files', [])
            for file in files:
                print(f"  - Tìm thấy file: {file.get('name')} (ID: {file.get('id')})")
                files_found[file.get('name')] = file.get('id')
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        if not files_found:
            print(f"-> Không tìm thấy file Word (.docx) nào trong thư mục {folder_id}.")
        else:
             print(f"-> Đã tìm thấy tổng cộng {len(files_found)} file Word.")
        return dict(sorted(files_found.items()))
    except HttpError as error:
        print(f'LỖI HttpError khi lấy danh sách file từ Drive: {error}')
        return {}
    except Exception as e:
        print(f'LỖI không xác định khi lấy danh sách file từ Drive: {e}')
        return {}

def load_word_file_contents(file_ids_dict):
    """Tải và đọc nội dung text từ các file Word dựa vào dictionary {tên file: id file}."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE or not file_ids_dict:
        print("(!) Bỏ qua tải nội dung file Word: Drive chưa kết nối hoặc không có file ID.")
        return {}

    contents = {}
    total_files = len(file_ids_dict)
    print(f"-> Bắt đầu tải và đọc nội dung cho {total_files} file Word...")
    count = 0
    for file_name, file_id in file_ids_dict.items():
        count += 1
        try:
            request_obj = DRIVE_SERVICE.files().get_media(fileId=file_id)
            file_content_bytes = request_obj.execute()
            with io.BytesIO(file_content_bytes) as f:
                document = Document(f)
                full_text = [para.text for para in document.paragraphs if para.text.strip()]
                contents[file_name] = '\n'.join(full_text)
            print(f"  - [{count}/{total_files}] Đã đọc xong: {file_name}")
        except HttpError as error:
            print(f'  - LỖI HttpError khi tải file {file_name} (ID: {file_id}): {error}')
        except Exception as e:
            print(f'  - LỖI {type(e).__name__} khi xử lý file {file_name} (ID: {file_id}): {e}')
    print(f"-> Hoàn tất đọc nội dung các file word. Đã đọc thành công {len(contents)}/{total_files} file.")
    return contents

# Các hàm xử lý file excel
def get_all_excel_files(folder_id):
    """Lấy danh sách tên và ID các file Excel (.xlsx) trong thư mục Google Drive chỉ định."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE:
        print("(!) Bỏ qua lấy file Excel: Kết nối Google Drive chưa được thiết lập.")
        return {}
    if not folder_id:
        print("(!) Bỏ qua lấy file Excel: DRIVE_FOLDER_ID chưa được thiết lập.")
        return {}

    files_found = {}
    page_token = None
    print(f"-> Bắt đầu tìm file Excel trong thư mục Drive ID: {folder_id}...")
    try:
        while True:
            response = DRIVE_SERVICE.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageToken=page_token
            ).execute()
            files = response.get('files', [])
            for file in files:
                print(f"  - Tìm thấy file: {file.get('name')} (ID: {file.get('id')})")
                files_found[file.get('name')] = file.get('id')
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        if not files_found:
            print(f"-> Không tìm thấy file Excel (.xlsx) nào trong thư mục {folder_id}.")
        else:
            print(f"-> Đã tìm thấy tổng cộng {len(files_found)} file Excel.")
        return dict(sorted(files_found.items()))
    except HttpError as error:
        print(f'LỖI HttpError khi lấy danh sách file Excel từ Drive: {error}')
        return {}
    except Exception as e:
        print(f'LỖI không xác định khi lấy danh sách file Excel từ Drive: {e}')
        return {}
    
def load_excel_file_contents(file_ids_dict):
    """Tải và đọc nội dung text từ các file Excel dựa vào dictionary {tên file: id file}."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE or not file_ids_dict:
        print("(!) Bỏ qua tải nội dung file Excel: Drive chưa kết nối hoặc không có file ID.")
        return {}

    contents = {}
    total_files = len(file_ids_dict)
    print(f"-> Bắt đầu tải và đọc nội dung cho {total_files} file Excel...")
    count = 0
    for file_name, file_id in file_ids_dict.items():
        count += 1
        try:
            request_obj = DRIVE_SERVICE.files().get_media(fileId=file_id)
            file_content_bytes = request_obj.execute()

            # Đọc Excel từ byte stream
            workbook = openpyxl.load_workbook(io.BytesIO(file_content_bytes), data_only=True)
            content = f"\n=== [Excel] {file_name} ===\n"
            for sheet in workbook.worksheets:
                content += f"\n--- Sheet: {sheet.title} ---\n"
                for row in sheet.iter_rows(values_only=True):
                    line = " | ".join([str(cell) if cell is not None else "" for cell in row])
                    content += line + "\n"
            contents[file_name] = content

            print(f"  - [{count}/{total_files}] Đã đọc xong: {file_name}")
        except HttpError as error:
            print(f'  - LỖI HttpError khi tải file {file_name} (ID: {file_id}): {error}')
        except Exception as e:
            print(f'  - LỖI {type(e).__name__} khi xử lý file {file_name} (ID: {file_id}): {e}')
    print(f"-> Hoàn tất đọc nội dung các file excel. Đã đọc thành công {len(contents)}/{total_files} file.")
    return contents


# --- Hàm ghi log chat vào Google Sheet ---
def setup_sheet_service():
    global SHEET_SERVICE
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(SERVICE_ACCOUNT_INFO_JSON),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        SHEET_SERVICE = build_sheet('sheets', 'v4', credentials=creds)
    except Exception as e:
        print(f"LỖI khi kết nối Google Sheets: {e}")

def log_to_sheet(employee_id, question, answer):
    if not SHEET_SERVICE or not SHEET_ID:
        print("(!) Không có kết nối Google Sheets. Bỏ qua ghi log.")
        return

    ho_ten = EMPLOYEE_NAME_MAP.get(employee_id, employee_id)
    vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh") # Lấy giờ Việt Nam
    timestamp = datetime.now(vietnam_tz).strftime("%Y-%m-%d %H:%M:%S")
    values = [[ho_ten, timestamp, question, answer]]
    body = {'values': values}

    try:
        sheet = SHEET_SERVICE.spreadsheets()
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range='A:D',
            valueInputOption='RAW',
            body=body
        ).execute()
        print(f"-> Đã ghi log: {ho_ten} - {timestamp}")
    except SheetHttpError as e:
        print(f"LỖI khi ghi log vào Google Sheet: {e}")

# Hàm lấy chatlog từ Google Sheet đưa vào dữ liệu tham khảo cho VIBA
def get_chat_history(employee_id, limit=10):
    """Lấy lịch sử chat gần nhất của cán bộ từ Google Sheet."""
    if not SHEET_SERVICE or not SHEET_ID:
        return ""
    try:
        sheet = SHEET_SERVICE.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SHEET_ID,
            range='A2:D'
        ).execute()
        logs = result.get('values', [])
        # Lọc theo employee_id (hoặc tên)
        history = [
            f"Hỏi: {row[2]}\nĐáp: {row[3]}"
            for row in logs if row[0] == EMPLOYEE_NAME_MAP.get(employee_id, employee_id)
        ]
        # Lấy limit câu gần nhất
        return "\n\n".join(history[-limit:])
    except Exception as e:
        print(f"Lỗi khi lấy lịch sử chat: {e}")
        return ""

# === Các Route của Flask ===
@app.route('/') #Hiển thị trang chính
def index():
    """Route chính, trả về trang giao diện chat (index.html)."""
    print("[Route] GET / - Hiển thị trang chat.")
    # Đảm bảo file index.html nằm trong thư mục 'templates' cùng cấp với app.py
    return render_template('index.html')

# --- Route /verify_employee giữ nguyên ---
@app.route('/verify_employee', methods=['POST'])
def verify_employee():
    """API Endpoint để xác thực mã cán bộ từ file CSV."""
    print("[Route] POST /verify_employee - Nhận yêu cầu xác thực mã cán bộ.")
    data = request.get_json()
    if not data or 'employee_id' not in data:
         print("(!) Lỗi yêu cầu: Thiếu employee_id trong JSON.")
         return jsonify({'status': 'error', 'message': 'Yêu cầu không hợp lệ, thiếu employee_id.'}), 400

    employee_id = data['employee_id'].strip()
    if not employee_id:
        print("(!) Lỗi yêu cầu: employee_id rỗng.")
        return jsonify({'status': 'error', 'message': 'Mã cán bộ không được để trống.'}), 400

    print(f"  - Đang tìm kiếm mã cán bộ: '{employee_id}'")
    # Kiểm tra xem file dữ liệu cán bộ có tồn tại không
    if not os.path.exists(EMPLOYEE_DATA_FILE):
         print(f"LỖI NGHIÊM TRỌNG: Không tìm thấy file dữ liệu '{EMPLOYEE_DATA_FILE}'.")
         return jsonify({'status': 'error', 'message': 'Lỗi hệ thống, không thể xác thực. Vui lòng liên hệ quản trị viên.'}), 500

    try:
        with open(EMPLOYEE_DATA_FILE, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            required_columns = ['ma_can_bo', 'ho_ten', 'chuc_vu']
            if not all(col in reader.fieldnames for col in required_columns):
                print(f"LỖI: File CSV '{EMPLOYEE_DATA_FILE}' thiếu các cột cần thiết ({', '.join(required_columns)}).")
                return jsonify({'status': 'error', 'message': 'Lỗi cấu trúc file dữ liệu. Vui lòng liên hệ quản trị viên.'}), 500

            for row in reader:
                if row.get('ma_can_bo', '').strip() == employee_id:
                    ho_ten = row.get('ho_ten', 'N/A').strip()
                    chuc_vu = row.get('chuc_vu', '').strip()
                    greeting = f"Mã cán bộ {employee_id} đã được xác nhận. Xin chào {chuc_vu} - {ho_ten}!"
                    EMPLOYEE_NAME_MAP[employee_id] = ho_ten  # Gán tên cán bộ vào mã cán bộ để lưu chatlogs theo tên
                    # FILES được load khi khởi động ứng dụng
                    file_list = list(WORD_FILES.keys()) + list(EXCEL_FILES.keys())
                    print(f"  -> Xác nhận thành công: Mã {employee_id} -> {chuc_vu} {ho_ten}.")
                    print(f"  -> Gửi về {len(file_list)} tên file Word.")
                    return jsonify({
                        'status': 'success',
                        'greeting': greeting,
                        'file_list': file_list
                    })

            print(f"  -> Xác nhận thất bại: Mã '{employee_id}' không tồn tại trong file.")
            return jsonify({'status': 'error', 'message': 'Mã cán bộ không tồn tại hoặc không đúng. Vui lòng thử lại.'})
    except FileNotFoundError:
         print(f"LỖI FileNotFoundError: Không thể mở file '{EMPLOYEE_DATA_FILE}' dù đã kiểm tra tồn tại.")
         return jsonify({'status': 'error', 'message': 'Lỗi hệ thống, không thể đọc dữ liệu. Vui lòng liên hệ quản trị viên.'}), 500
    except Exception as e:
        print(f"LỖI không xác định khi xử lý file CSV hoặc xác thực: {e}")
        return jsonify({'status': 'error', 'message': 'Đã xảy ra lỗi trong quá trình xác thực. Vui lòng thử lại sau.'}), 500
    EMPLOYEE_NAME_MAP[employee_id] = ho_ten
# Tạo phiên chat riêng cho từng cán bộ
def get_or_create_chat_session(employee_id):
    """Lấy hoặc tạo phiên chat riêng cho mỗi mã cán bộ."""
    global CHAT_SESSIONS

    if employee_id in CHAT_SESSIONS:
        return CHAT_SESSIONS[employee_id]

    model = genai.GenerativeModel(model_name=MODEL_NAME,
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)

    all_contents = {**WORD_CONTENTS, **EXCEL_CONTENTS}  # Dữ liệu từ cả file Word và Excel
    all_context = ""
    for file_name, content in all_contents.items():
        all_context += f"[Tệp: {file_name}]\n{content.strip()}\n\n"

    chat_history = get_chat_history(employee_id, limit=10) # Lịch sử chat gần nhất

    context_prompt = f"""
Bạn là trợ lý AI thông minh tên là VIBA, do Nguyễn Thái Hùng tạo ra để hỗ trợ cán bộ BIDV Bắc Hải Dương dựa phần lớn vào tài liệu đã được cung cấp.
Bạn là trợ lý AI thông minh nhưng hãy tự coi mình là một người đồng nghiệp của cán bộ BIDV Bắc Hải Dương.
Người dùng là cán bộ BIDV Bắc Hải Dương nên bạn không được phép trả lời theo kiểu để biết thêm chi tiết, để biết thông tin chính xác nên liên hệ với BIDV Bắc Hải Dương hoặc kiểm trả trên website BIDV.
Bạn vẫn có thể trả lời các câu hỏi liên quan đến ngân hàng, sản phẩm, dịch vụ, quy trình làm việc và các vấn đề liên quan đến ngân hàng.
Bạn có thể tham khảo cả các nguồn thông tin khác từ internet và bộ nhớ thông minh của bạn để trả lời câu hỏi.
Hãy trả lời câu hỏi một cách tự nhiên và thân thiện, giống như một người bạn đồng hành.
Nếu câu hỏi không rõ ràng, hãy yêu cầu người dùng cung cấp thêm thông tin để có thể trả lời chính xác hơn.
Hãy ghi nhớ những câu hỏi và câu trả lời trước đó để có thể tham khảo trong các câu hỏi sau.
Dưới đây là toàn bộ thông tin cần ghi nhớ để trả lời các câu hỏi sau này:
1. Thông tin từ các văn bản Word và Excel đã tải về từ Google Drive:
<<<
{all_context}
>>>
2. Các nội dung cần lưu ý:
Các câu hỏi liên quan tới biểu phí: Hãy phân biệt rõ phí đối với các hạng khách hàng (Phổ thông, Premier và Premier elite) nếu người dùng không chỉ định rõ.
Các câu hỏi về phí nếu người dùng hỏi cho một trường hợp cụ thể hãy cố gắng tính toán và đưa ra con số cụ thể.
3. Lịch sử câu hỏi và câu trả lời trước đó:
Hãy tham khảo những câu hỏi và câu trả lời trước đây của người dùng này để hiểu rõ hơn về câu hỏi của họ.
<<<
{chat_history}
>>>
4. Thông tin thêm về ứng dụng VIBA và tác giả:
<<<
{hungdaica}
>>>
Hãy ghi nhớ và sử dụng thông tin này trong suốt cuộc hội thoại.
"""
    chat_session = model.start_chat(history=[{"role": "user", "parts": [context_prompt]}])
    CHAT_SESSIONS[employee_id] = chat_session
    print(f"-> Đã tạo phiên chat mới cho cán bộ {employee_id}")
    return chat_session
# --- Route /ask phiên chat theo mã cán bộ ---
@app.route('/ask', methods=['POST'])
def ask():
    """API trả lời câu hỏi, dùng phiên chat riêng theo mã cán bộ."""
    print("[Route] POST /ask - Nhận câu hỏi từ người dùng.")
    data = request.get_json()

    # Kiểm tra input
    question = data.get('question', '').strip()
    employee_id = data.get('employee_id', '').strip()

    if not question:
        return jsonify({'error': 'Câu hỏi không được để trống.'}), 400
    if not employee_id:
        return jsonify({'error': 'Thiếu mã cán bộ.'}), 400

    print(f"  - Mã cán bộ: {employee_id} | Câu hỏi: \"{question}\"")

    try:
        chat_session = get_or_create_chat_session(employee_id)
        response = chat_session.send_message(question)
        print("  -> Nhận được câu trả lời từ Gemini.")
        # Ghi log câu hỏi và câu trả lời vào Google Sheet
        answer_text = response.text
        log_to_sheet(employee_id, question, answer_text)
        return jsonify({'answer': answer_text})
    except Exception as e:
        print(f"LỖI khi gọi Gemini API: {e}")
        return jsonify({'error': f'Đã xảy ra lỗi khi giao tiếp với AI. Vui lòng thử lại sau.'}), 500

# --- Route /logchat để xem log chat ---
@app.route('/chatlog', methods=['GET', 'POST'])
def chatlog():
    error = None
    logs = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            try:
                result = SHEET_SERVICE.spreadsheets().values().get(
                    spreadsheetId=SHEET_ID,
                    range='A2:D'
                ).execute()
                logs = result.get('values', [])
            except Exception as e:
                error = f"Lỗi khi đọc dữ liệu: {e}"
        else:
            error = "Sai mật khẩu. Vui lòng thử lại."
    return render_template('chatlog.html', error=error, logs=logs)

# === Khối thực thi chính khi chạy file app.py (chỉ chạy khi start bằng python app.py) ===
""" Deploy: Nếu chạy trên Render thì thay đổi điều kiện này thành __name__ != '__main__' """

if __name__ != '__main__': 
    print("="*30)
    print("KHỞI TẠO ỨNG DỤNG VIBA AI CHAT")
    print("="*30)

    # Bước 1/6: Kiểm tra kết nối tới Gemini API
    print("\n[Bước 1/6] Kiểm tra kết nối tới Gemini API...")
    if GOOGLE_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            print("-> Đã kết nối Gemini API thành công.")
        except Exception as e:
            print(f"LỖI CẤU HÌNH GEMINI API: {e}. Kiểm tra API Key.")
    else:
        print("LỖI: Biến môi trường GOOGLE_API_KEY chưa được thiết lập.")

    # Bước 2/6: Kiểm tra dữ liệu cán bộ
    print(f"\n[Bước 2/6] Kiểm tra file dữ liệu cán bộ ...")
    if not os.path.exists(EMPLOYEE_DATA_FILE):
        print(f"Lỗi: Không tìm thấy file dữ liệu cán bộ!")
        print(" -> Chức năng xác thực mã cán bộ sẽ KHÔNG hoạt động.")
    else:
        print(f"-> Chức năng xác thực mã cán bộ đã sẵn sàng.")

    # Bước 3/6: Kiểm tra kết nối tới Google Drive
    print("\n[Bước 3/6] Kiểm tra kết nối tới Google Drive...")
    setup_drive_service()
    if not DRIVE_SERVICE:
        print("LỖI: Không thể kết nối Google Drive API.")
    else:
        print("-> Đã kết nối Google Drive API thành công.")

    # Bước 4/6: Tải dữ liệu văn bản từ Google Drive
    print("\n[Bước 4/6] Tải dữ liệu văn bản từ Google Drive...")
    if DRIVE_SERVICE and DRIVE_FOLDER_ID:
        WORD_FILES = get_all_word_files(DRIVE_FOLDER_ID)
        if WORD_FILES:
            WORD_CONTENTS = load_word_file_contents(WORD_FILES)
        else:
            WORD_FILES = {}
            WORD_CONTENTS = {}
        EXCEL_FILES = get_all_excel_files(DRIVE_FOLDER_ID)
        if EXCEL_FILES:
            EXCEL_CONTENTS = load_excel_file_contents(EXCEL_FILES)
        else:
            EXCEL_FILES = {}
            EXCEL_CONTENTS = {}
    else:
        print("-> Không tải được văn bản do không có kết nối Google Drive hoặc thiếu Folder ID.")
        WORD_FILES = {}
        WORD_CONTENTS = {}
        EXCEL_FILES = {}
        EXCEL_CONTENTS = {}

    # Bước 5/6: Tải lịch sử chat (test thử lấy lịch sử của 1 cán bộ đầu tiên nếu có)
    print("\n[Bước 5/6] Tải lịch sử chat...")
    test_emp_id = next(iter(WORD_FILES), None)
    if test_emp_id:
        try:
            test_history = get_chat_history(test_emp_id, limit=1)
            print("-> Lấy lịch sử chat thành công.")
        except Exception as e:
            print(f"LỖI khi lấy lịch sử chat: {e}")
    else:
        print("-> Không có lịch sử chat.")

    # Bước 6/6: Thiết lập Google Sheet để lưu chatlog
    print("\n[Bước 6/6] Thiết lập Google Sheet để lưu chatlog...")
    setup_sheet_service()
    if not SHEET_SERVICE:
        print("(!) Không thể kết nối Google Sheets API. Không thể ghi chatlog.")
    else:
        print("-> Đã kết nối Google Sheets API thành công.")

    # Tổng kết
    print("\n" + "="*30)
    print("KHỞI TẠO HOÀN TẤT!")
    print(f"- Trạng thái Gemini API: {'Đã kết nối' if GOOGLE_API_KEY else 'Không kết nối / Lỗi cấu hình'}")
    print(f"- Trạng thái Google Drive: {'Đã kết nối' if DRIVE_SERVICE else 'Không kết nối / Lỗi cấu hình'}")
    print(f"- Trạng thái Google Sheets: {'Đã kết nối' if SHEET_SERVICE else 'Không kết nối / Lỗi cấu hình'}")
    print(f"- Dữ liệu cán bộ: {'Sẵn sàng' if os.path.exists(EMPLOYEE_DATA_FILE) else 'Không tìm thấy'}")
    print(f"- Số file Word được tải: {len(WORD_FILES)}")
    print(f"- Số file Excel được tải: {len(EXCEL_FILES)}")
    print("="*30)

    # Khởi động Flask server localhost
    """ Deploy: Nếu chạy trên Render thì xóa app.run() đi, Render sẽ tự động chạy Gunicorn """
    #app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    #print("\n-> Khởi động Flask development server...")
    #print("   Truy cập ứng dụng tại: http://127.0.0.1:5000 (hoặc địa chỉ IP của máy nếu host='0.0.0.0')")
    # debug=True: tự động reload khi có thay đổi code, hiển thị lỗi chi tiết
    # host='0.0.0.0': cho phép truy cập từ các máy khác trong cùng mạng LAN
    # port=5000: cổng mặc định của Flask
