import os, time
from flask import Flask, jsonify, request
import cv2
import numpy as np
import boto3
import io
import tempfile
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,ImageSendMessage,ImageMessage, VideoMessage, AudioMessage
)
line_bot_api = LineBotApi('填入Channel access token')
handler = WebhookHandler('填入Channel secret')
app = Flask(__name__)

# -----------------------yolo setting-----------------------------
modelType = "yolo-tiny"  # yolo or yolo-tiny
#modelType = "yolo"  # yolo or yolo-tiny
confThreshold = 0.4  # Confidence threshold
nmsThreshold = 0.6  # Non-maximum suppression threshold
classesFile = "obj.names";
modelConfiguration = "yolov3-tiny.cfg";
modelWeights = "yolov3-tiny.weights";
#modelConfiguration = "yolov3.cfg";
#modelWeights = "yolov3.weights";
# Label & Box
fontSize = 0.55
fontBold = 2
labelColor = (0, 0, 255)
boxbold = 3
boxColor = (0, 0, 255)
# --------------------------------------------------------

if (modelType == "yolo"):
    inpWidth = 608  # Width of network's input image
    inpHeight = 608  # Height of network's input image
else:
    inpWidth = 416  # Width of network's input image
    inpHeight = 416  # Height of network's input image

# -----------------------yolo class and model loading-----------------------------
classes = None
with open(classesFile, 'rt') as f:
    classes = f.read().rstrip('\n').split('\n')
net = cv2.dnn.readNetFromDarknet(modelConfiguration, modelWeights)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
# ------------------------------------------------------------------------------
# -------------------------aws S3 certificate setting------------------------------
S3_BUCKET = '填入aws s3上所建立的BUCKET名稱'
# S3_BUCKET = os.environ.get('S3_BUCKET')
Access_Key_Id = '填入aws上建立的access key id'
Secret_Access_Key = '填入aws上建立的secret access key'
# ---------------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
	signature = request.headers['X-Line-Signature']

    # get request body as text
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		abort(400)

	return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    userId = event.source.user_id
    #profile = line_bot_api.get_profile(userId)
    replay_message = event.message.text
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=replay_message))

@handler.add(MessageEvent, message=(ImageMessage))
def handle_content_message(event):
    userId = event.source.user_id
    message_content = line_bot_api.get_message_content(event.message.id)
    line_message = '已收到您的圖片，辨識中。請稍後......' + '\n'
    line_bot_api.push_message(userId, TextSendMessage(text=line_message))
    image = cv2.imdecode(np.fromstring(message_content.content, np.uint8), cv2.IMREAD_UNCHANGED)
    orgFrame = image.copy()

    blob = cv2.dnn.blobFromImage(image, 1 / 255, (inpWidth, inpHeight), [0, 0, 0], 1, crop=False)
    net.setInput(blob)
    outs = net.forward(getOutputsNames(net))
    resultDic = postprocess(image, outs, orgFrame)
    outputFile = 'result_yolo.jpg'
    #outputFile = 'result_yolo_' + str(time.time()).split('.')[0] + '.jpg'
    is_success, buffer = cv2.imencode(".jpg", orgFrame.astype(np.uint8))
    io_buf = io.BytesIO(buffer)

    s3 = boto3.resource('s3', aws_access_key_id=Access_Key_Id,
                        aws_secret_access_key=Secret_Access_Key)
    s3.Bucket(S3_BUCKET).put_object(Key=outputFile, Body=io_buf)

    s3_client = boto3.client('s3', aws_access_key_id=Access_Key_Id,
                             aws_secret_access_key=Secret_Access_Key)
    params = {'Bucket': S3_BUCKET, 'Key': outputFile, 'ResponseContentType': 'jpg'}
    url = s3_client.generate_presigned_url('get_object', params)

    image_message = ImageSendMessage(
        original_content_url=url,
        preview_image_url=url
    )
    line_bot_api.push_message(userId, image_message)
    reponse = {
        "image": url,
        "result": resultDic
    }
    return jsonify(reponse)

@app.route('/detection', methods=['POST'])
def detection():
    print(request)
    if request.method == 'POST' and request.files['image']:
        file = request.files['image']
        # Read image
        image = cv2.imdecode(np.fromstring(file.read(), np.uint8), cv2.IMREAD_UNCHANGED)
        orgFrame = image.copy()

        blob = cv2.dnn.blobFromImage(image, 1 / 255, (inpWidth, inpHeight), [0, 0, 0], 1, crop=False)
        net.setInput(blob)
        outs = net.forward(getOutputsNames(net))
        resultDic = postprocess(image, outs, orgFrame)
        outputFile = 'result_yolo.jpg'
        is_success, buffer = cv2.imencode(".jpg",  orgFrame.astype(np.uint8))
        io_buf = io.BytesIO(buffer)

        s3 = boto3.resource('s3',aws_access_key_id=Access_Key_Id,aws_secret_access_key=Secret_Access_Key)
        s3.Bucket(S3_BUCKET).put_object(Key=outputFile, Body=io_buf)

        s3_client = boto3.client('s3',aws_access_key_id=Access_Key_Id,aws_secret_access_key=Secret_Access_Key)
        params = {'Bucket': S3_BUCKET, 'Key': outputFile,'ResponseContentType': 'jpg'}
        url = s3_client.generate_presigned_url('get_object', params)

        reponse = {
            "image": url,
            "result": resultDic
        }
        return jsonify(reponse)
    else:
        return "fail"

# -----------------------------------------------------------------
# Get the names of the output layers
def getOutputsNames(net):
    layersNames = net.getLayerNames()
    return [layersNames[i[0] - 1] for i in net.getUnconnectedOutLayers()]

def postprocess(frame, outs, orgFrame):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    classIds = []
    confidences = []
    boxes = []
    for out in outs:
        for detection in out:
            scores = detection[5:]
            classId = np.argmax(scores)
            confidence = scores[classId]
            if confidence > confThreshold:
                center_x = int(detection[0] * frameWidth)
                center_y = int(detection[1] * frameHeight)
                width = int(detection[2] * frameWidth)
                height = int(detection[3] * frameHeight)
                left = int(center_x - width / 2)
                top = int(center_y - height / 2)
                classIds.append(classId)
                confidences.append(float(confidence))
                boxes.append([left, top, width, height])

    indices = cv2.dnn.NMSBoxes(boxes, confidences, confThreshold, nmsThreshold)
    resultDic = {}
    for i in indices:
        i = i[0]
        box = boxes[i]
        left = box[0]
        top = box[1]
        width = box[2]
        height = box[3]
        drawPred(classIds[i], confidences[i], left, top, left + width, top + height, orgFrame)
        resultDic[classes[classIds[i]]] = confidences[i]
    return resultDic

def drawPred(classId, conf, left, top, right, bottom, orgFrame):
    label = '%.2f' % conf
    labelName = '%s:%s' % (classes[classId], label)
    cv2.rectangle(orgFrame, (left, top), (right, bottom), boxColor, boxbold)
    cv2.putText(orgFrame, labelName, (left, top - 10), cv2.FONT_HERSHEY_COMPLEX, fontSize, labelColor, fontBold)
    print(labelName)


if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)