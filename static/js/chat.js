// === Lấy các phần tử DOM cần thiết ===
        const chatContainer = document.getElementById('chat-container');
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        const loadingIndicator = document.getElementById('loading-indicator');
        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = `${messageInput.scrollHeight}px`;
        });

        // === Biến trạng thái ===
        let isVerified = false; // Theo dõi trạng thái xác thực mã cán bộ
        let currentEmployeeId = null; // Lưu mã cán bộ đã xác thực (nếu cần)

        // === Các hàm trợ giúp ===

        /**
         * Thêm dấu thời gian vào cuối một phần tử tin nhắn.
         * @param {HTMLElement} messageElement Phần tử div của tin nhắn.
         */
        function addTimestamp(messageElement) {
            const now = new Date();
            // Định dạng thời gian HH:MM (ví dụ: 09:05)
            const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
            const timestampSpan = document.createElement('span');
            timestampSpan.classList.add('timestamp');
            timestampSpan.textContent = timeString;
            messageElement.appendChild(timestampSpan); // Thêm vào cuối tin nhắn
        }

        /**
         * Hiển thị hiệu ứng gõ chữ cho tin nhắn AI.
         * @param {HTMLElement} element Phần tử div của tin nhắn AI.
         * @param {string} text Nội dung tin nhắn cần hiển thị.
         * @param {function} [callback] Hàm được gọi sau khi gõ xong.
         */
        function typeEffect(element, text, callback) {
            let i = 0;
            const speed = 20; // Tốc độ gõ (ms/ký tự), giảm để nhanh hơn
            element.textContent = ''; // Xóa nội dung cũ (nếu có)
            chatContainer.scrollTop = chatContainer.scrollHeight; // Cuộn xuống khi bắt đầu gõ

            function typeCharacter() {
                if (i < text.length) {
                    element.textContent += text.charAt(i); // Thêm từng ký tự
                    i++;
                    // Tiếp tục cuộn xuống trong quá trình gõ
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    // Đặt hẹn giờ để gõ ký tự tiếp theo
                    setTimeout(typeCharacter, speed);
                } else {
                    // Gõ xong, thêm dấu thời gian
                    addTimestamp(element);
                    // Đảm bảo cuộn xuống lần cuối
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    // Gọi hàm callback nếu có
                    if (callback) {
                        callback();
                    }
                }
            }
            typeCharacter(); // Bắt đầu quá trình gõ
        }

        /**
         * Thêm một tin nhắn mới vào khung chat.
         * @param {string} text Nội dung tin nhắn.
         * @param {'user' | 'ai'} sender Người gửi ('user' hoặc 'ai').
         * @param {boolean} [useTypingEffect=false] Có sử dụng hiệu ứng gõ chữ cho tin nhắn AI không.
         * @param {function} [callback] Hàm được gọi sau khi tin nhắn hiển thị xong (hoặc gõ xong).
         */
        function addMessageToChat(text, sender, useTypingEffect = false, callback) {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('message', `${sender}-message`); // Thêm class chung và class riêng

            // Đặt nội dung ban đầu là khoảng trắng để tránh bị thu nhỏ trước khi có nội dung
            messageDiv.textContent = ' ';

            // Thêm tin nhắn vào DOM
            chatContainer.appendChild(messageDiv);

            if (sender === 'user') {
                messageDiv.textContent = text; // Hiển thị ngay lập tức
                addTimestamp(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight; // Cuộn xuống
                if (callback) callback(); // Gọi callback ngay nếu có
            } else if (sender === 'ai') {
                if (useTypingEffect) {
                    // Gán text trước để typeEffect có thể lấy độ dài
                    messageDiv.textContent = text;
                    typeEffect(messageDiv, text, callback); // Sử dụng hiệu ứng gõ
                } else {
                    messageDiv.textContent = text; // Hiển thị ngay không hiệu ứng
                    addTimestamp(messageDiv);
                    chatContainer.scrollTop = chatContainer.scrollHeight; // Cuộn xuống
                    if (callback) callback(); // Gọi callback ngay nếu có
                }
            }
             // Đảm bảo cuộn xuống cuối cùng sau khi thêm tin nhắn
             // Dùng setTimeout nhỏ để đảm bảo trình duyệt đã render xong tin nhắn mới
             setTimeout(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
             }, 50);
        }

        /** Kích hoạt ô nhập liệu và nút gửi cho việc đặt câu hỏi. */
        function enableInputForQuestions() {
            messageInput.placeholder = 'Nhập câu hỏi của bạn...';
            messageInput.disabled = false;
            sendButton.disabled = false;
            sendButton.title = 'Gửi câu hỏi'; // Cập nhật tooltip
            messageInput.focus(); // Focus vào ô nhập liệu
        }

        /** Kích hoạt ô nhập liệu và nút gửi để người dùng nhập lại mã cán bộ. */
        function enableInputForRetryVerification() {
            messageInput.placeholder = 'Mã không đúng. Vui lòng nhập lại Mã cán bộ...';
            messageInput.disabled = false;
            sendButton.disabled = false;
             sendButton.title = 'Gửi Mã cán bộ'; // Cập nhật tooltip
            messageInput.focus();
        }

        /** Vô hiệu hóa ô nhập liệu và nút gửi. */
        function disableInput() {
             messageInput.disabled = true;
             sendButton.disabled = true;
             sendButton.title = 'Đang xử lý...';
        }

        // === Hàm xử lý chính khi gửi tin nhắn ===
        async function handleSend() {
            const messageText = messageInput.value.trim(); // Lấy nội dung và xóa khoảng trắng thừa
            if (!messageText) return; // Không gửi nếu nội dung rỗng

            // 1. Hiển thị tin nhắn của người dùng ngay lập tức
            addMessageToChat(messageText, 'user');
            const userMessageToSend = messageInput.value; // Lưu lại giá trị trước khi xóa
            messageInput.value = ''; // Xóa nội dung trong ô nhập

            // 2. Vô hiệu hóa input và hiển thị chỉ báo đang tải
            disableInput();
            loadingIndicator.textContent = 'Đang xử lý yêu cầu...';
            loadingIndicator.style.display = 'block'; // Hiện chỉ báo
            chatContainer.scrollTop = chatContainer.scrollHeight; // Cuộn xuống

            // 3. Kiểm tra xem đang ở giai đoạn xác thực hay hỏi đáp
            if (!isVerified) {
                // --- Giai đoạn Xác thực Mã Cán bộ ---
                loadingIndicator.textContent = 'Đang xác thực Mã cán bộ...';
                try {
                    // Gọi API backend để xác thực
                    const response = await fetch('/verify_employee', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ employee_id: userMessageToSend }) // Gửi mã cán bộ
                    });

                    // Nhận và xử lý kết quả JSON từ backend
                    const data = await response.json();
                    loadingIndicator.style.display = 'none'; // Ẩn chỉ báo tải

                    if (response.ok && data.status === 'success') {
                        // --- Xác thực Thành công ---
                        isVerified = true; // Chuyển trạng thái đã xác thực
                        currentEmployeeId = userMessageToSend; // Lưu lại mã (nếu cần)

                        // Hiển thị lời chào từ AI
                        addMessageToChat(data.greeting, 'ai', true, () => {
                            // Callback được gọi SAU KHI lời chào hiển thị xong

                            // Kiểm tra xem có danh sách file từ backend không
                            if (data.file_list && data.file_list.length > 0) {
                                // Có danh sách file -> Tạo và hiển thị tin nhắn liệt kê file
                                let fileListMessage = " Tôi có thể hỗ trợ bạn trên cơ sở nội dung của các văn bản sau:\n";
                                data.file_list.forEach((fileName, index) => {
                                    fileListMessage += `${index + 1}. ${fileName}\n`;
                                });
                                fileListMessage = fileListMessage.trim(); // Xóa dòng trống cuối
                                fileListMessage += "\n Ngoài ra tôi cũng có thể trả lời các câu hỏi khác như một trợ lý ảo thông minh.";
                                fileListMessage += "\n Xin mời đặt câu hỏi.";

                                // Hiển thị danh sách file (cũng dùng hiệu ứng gõ)
                                addMessageToChat(fileListMessage, 'ai', true, () => {
                                    // Callback được gọi SAU KHI danh sách file hiển thị xong
                                    enableInputForQuestions(); // Kích hoạt input để đặt câu hỏi
                                });
                            } else {
                                // Không có danh sách file -> Hiển thị câu hỏi chung và kích hoạt input
                                addMessageToChat("Bạn cần hỗ trợ gì tiếp theo?", 'ai', true, () => {
                                     // Callback được gọi SAU KHI câu hỏi này hiển thị xong
                                    enableInputForQuestions(); // Kích hoạt input để đặt câu hỏi
                                });
                            }
                        });

                    } else {
                        // --- Xác thực Thất bại ---
                        // Lấy thông báo lỗi từ server hoặc tạo thông báo chung
                        const errorMessage = data.message || `Lỗi ${response.status}: Không thể xác thực.`;
                        // Hiển thị lỗi và yêu cầu nhập lại
                        addMessageToChat(errorMessage, 'ai', true, () => {
                            enableInputForRetryVerification(); // Kích hoạt lại input để nhập mã
                        });
                    }
                } catch (error) {
                    // --- Lỗi Kết nối hoặc Fetch ---
                    console.error("Lỗi khi gọi /verify_employee:", error);
                    loadingIndicator.style.display = 'none';
                    // Hiển thị lỗi kết nối và yêu cầu thử lại
                    addMessageToChat("Lỗi kết nối đến máy chủ xác thực. Vui lòng kiểm tra lại Mã cán bộ và thử lại.", 'ai', true, () => {
                        enableInputForRetryVerification(); // Kích hoạt lại input để nhập mã
                    });
                }

            } else {
                // --- Giai đoạn Hỏi đáp thông thường ---
                loadingIndicator.textContent = 'VIBA AI đang trả lời...';
                try {
                    // Gọi API backend để hỏi AI
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: userMessageToSend,    // Gửi câu hỏi
                        employee_id: currentEmployeeId // gửi mã cán bộ đi cùng
                    })
                });

                    // Ẩn chỉ báo tải *trước khi* bắt đầu hiển thị câu trả lời
                    loadingIndicator.style.display = 'none';

                    // Xử lý lỗi HTTP từ backend
                    if (!response.ok) {
                         let errorMsg = `Lỗi HTTP: ${response.status}.`;
                         try {
                             // Cố gắng đọc thêm chi tiết lỗi từ JSON phản hồi (nếu có)
                             const errorData = await response.json();
                             errorMsg += ` ${errorData.error || 'Không có thông tin lỗi chi tiết.'}`;
                         } catch (e) { /* Bỏ qua nếu không đọc được JSON */ }
                         throw new Error(errorMsg); // Ném lỗi để bị bắt bởi khối catch bên dưới
                     }

                     // Nhận và xử lý kết quả JSON
                     const data = await response.json();

                     // Xử lý lỗi logic từ backend (ví dụ: Gemini báo lỗi)
                     if (data.error) {
                          throw new Error(data.error); // Ném lỗi để bị bắt bởi khối catch
                     }

                    // Hiển thị câu trả lời của AI
                    addMessageToChat(data.answer || "Xin lỗi, tôi không thể đưa ra câu trả lời vào lúc này.", 'ai', true, () => {
                        enableInputForQuestions(); // Kích hoạt lại input sau khi AI trả lời
                    });

                } catch (error) {
                    // --- Lỗi Kết nối, Fetch hoặc Lỗi từ backend/AI ---
                    console.error("Lỗi khi gọi /ask:", error);
                    loadingIndicator.style.display = 'none';
                    // Hiển thị thông báo lỗi chung cho người dùng
                    addMessageToChat(`Đã xảy ra lỗi khi xử lý câu hỏi: ${error.message}. Vui lòng thử lại.`, 'ai', true, () => {
                         enableInputForQuestions(); // Kích hoạt lại input
                    });
                }
            }
        }

        // === Gắn các sự kiện ===

        // Gửi khi nhấn nút
        sendButton.addEventListener('click', handleSend);

        // Gửi khi nhấn Enter trong ô input (chỉ khi không bị disable)
        messageInput.addEventListener('keypress', function (event) {
            if (event.key === 'Enter' && !messageInput.disabled) {
                event.preventDefault(); // Ngăn hành vi mặc định của Enter
                handleSend();
            }
        });

        // === Khởi tạo giao diện khi tải trang ===
        function initializeChat() {
            console.log("Khởi tạo giao diện chat...");
            const welcomeMessage = `Xin chào! Tôi là VIBA - Trợ lý ảo thông minh phục vụ cán bộ BIDV Bắc Hải Dương.
            Tôi có thể giúp bạn tra cứu văn bản nội bộ, trả lời câu hỏi nghiệp vụ và hỗ trợ thông tin một cách chính xác, nhanh chóng.
            Vui lòng nhập Mã cán bộ để bắt đầu.`;
            // Hiển thị tin nhắn chào mừng và yêu cầu mã cán bộ (không cần hiệu ứng gõ)
            addMessageToChat(welcomeMessage, 'ai', false, () => {
                // Callback được gọi sau khi tin nhắn đầu tiên hiển thị
                messageInput.placeholder = 'Nhập Mã cán bộ...'; // Đặt placeholder
                messageInput.disabled = false; // Kích hoạt ô nhập
                sendButton.disabled = false;  // Kích hoạt nút gửi
                sendButton.title = 'Gửi Mã cán bộ'; // Đặt tooltip cho nút
                messageInput.focus();         // Focus vào ô nhập liệu
                console.log("Giao diện sẵn sàng nhận Mã cán bộ.");
            });
        }

        // Chạy hàm khởi tạo sau khi toàn bộ cấu trúc HTML đã được tải xong
        document.addEventListener('DOMContentLoaded', initializeChat);