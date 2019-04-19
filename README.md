# flask_object_detection
###Step 1
Clone project
```
git clone https://github.com/jackscchen/flask_object_detection
```
###Step2
Setting line Message in main.py
```python
line_bot_api = LineBotApi('填入Channel access token')
handler = WebhookHandler('填入Channel secret')
```
###Step3
Setting AWS S3 certificate in main.py
```python
S3_BUCKET = '填入aws s3上所建立的BUCKET名稱'
Access_Key_Id = '填入aws上建立的access key id'
Secret_Access_Key = '填入aws上建立的secret access key'
```
[AWS免費帳號申請](https://aws.amazon.com/tw/free/)

[Heroku存取AWS S3設定值取得](https://devcenter.heroku.com/articles/s3)
###Step4
Heroku Setting (在windows的command line下執行，需先安裝Heroku CLI環境)
#####1. 登入heroku
```
heroku login
```
#####2. 建立app
```
heroku create app名稱
```
#####3. 將heroku的遠端git path加入
```
git remote add heroku https://git.heroku.com/app名稱.git
```
#####4. 加入python環境
```
heroku buildpacks:add heroku/python
```
#####5. 加入apt功能，是為了安裝opencv需要的lib，相關的lib定義在Aptfile中
```
heroku buildpacks:add --index 1 heroku-community/apt
```
###Step5
Push Code to Heroku
```
git push heroku master
```
###其它指令
```
heroku logs --tail #看heroku上的log訊息
heroku run bash --app app名稱 #連線至heroku上的機器，可下linux相關指令
```
