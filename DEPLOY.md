# 部署到 Render（讓別人用網址開啟）

部署後會得到一個網址（例如 `https://ats-hr.onrender.com`），任何電腦、手機都能開啟，不用在本機執行 `start.bat`。
打開網頁時會先要求輸入密碼，避免陌生人用掉我們的 Gemini 免費額度。

## 事前準備

1. **程式要先合併進 `main`**：Render 會部署 `main` 分支（設定在 `render.yaml` 的 `branch: main`）。
2. **GitHub 權限**：Render 需要讀取 `JessieHung123/ATS` 這個 repo。用 repo 擁有者的 GitHub 帳號操作最簡單；其他人操作時，需要擁有者在 GitHub 授權 Render 讀取這個 repo。
3. **Gemini API Key**：到 [Google AI Studio](https://aistudio.google.com/apikey) 申請（免費）。
4. **想好一組密碼**：全組共用，用來登入網站。建議至少 12 個字元，不要用生日或 `123456` 這類容易猜到的密碼。

## 部署步驟

1. 到 [render.com](https://render.com) 用 GitHub 帳號登入。
2. 右上角按 **New** → 選 **Blueprint**。
3. 選擇 `JessieHung123/ATS` 這個 repo。Render 會自動讀取 `render.yaml`，看到一個名為 `ats-hr` 的 Web Service。
4. Render 會請你填兩個值：
   - `GEMINI_API_KEY`：貼上 Gemini API Key。
   - `APP_PASSWORD`：填入全組共用的登入密碼。
5. 按 **Apply**（或 **Deploy Blueprint**），等待建置完成，第一次大約需要幾分鐘。
6. 狀態變成 **Live** 後，點服務頁面上方的網址就能開啟。

## 登入方式

打開網址時瀏覽器會跳出登入視窗：

- **使用者名稱**：隨意填（例如 `ats`）
- **密碼**：`APP_PASSWORD` 設定的那組密碼

同一個瀏覽器登入一次後，關閉瀏覽器前都不用再輸入。

## 之後的更新

程式 push 或合併到 GitHub 的 `main` 後，Render 會自動重新部署，幾分鐘後網站就是新版本。

要換 Key 或密碼：Render 服務頁面 → **Environment** → 修改 `GEMINI_API_KEY` 或 `APP_PASSWORD` → 儲存，Render 會自動重新啟動。

## 注意事項

- **免費方案會休眠**：一段時間沒人使用，服務會自動休眠；下一個人開啟時要等大約 1 分鐘才會醒來，之後就正常。正式展示前，建議先自己打開一次。
- **資料存在各自的瀏覽器**：職缺、候選人等資料存在每個人瀏覽器的 localStorage，伺服器不會保存；換電腦或換瀏覽器就看不到之前的資料。
- **只用虛構履歷**：履歷內容會經過 Render 的伺服器，再送到 Google Gemini；Gemini 免費版的內容可能被 Google 用於改善產品。
- **密碼只能擋一般人**：這是全組共用的簡易密碼，不要把網址和密碼貼在公開的地方。如果密碼外流，到 Render 的 **Environment** 改掉即可。
- **本機使用不受影響**：在自己電腦用 `start.bat` 執行時沒有設定 `APP_PASSWORD`，所以不需要密碼，跟原本一樣。
