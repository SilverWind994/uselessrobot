import datetime
import hashlib
import hmac
from urllib.parse import quote
import requests
import send_message as send
import base64
from io import BytesIO
from PIL import Image
import photo_opt
import re

Service = "cv"
Version = "2022-08-31"
Region = "cn-north-1"
Host = "visual.volcengineapi.com"
ContentType = "application/json"

AK = ""  # 已脱敏：火山引擎 Access Key
SK = ""  # 已脱敏：火山引擎 Secret Key


def norm_query(params):
    query = ""
    for key in sorted(params.keys()):
        if type(params[key]) == list:
            for k in params[key]:
                query = (
                        query + quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
                )
        else:
            query = (query + quote(key, safe="-_.~") + "=" + quote(params[key], safe="-_.~") + "&")
    query = query[:-1]
    return query.replace("+", "%20")

def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def request(method, date, query, header, ak, sk, action, body):
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": Service,
        "region": Region,
    }
    request_param = {
        "body": body,
        "host": Host,
        "path": "/",
        "method": method,
        "content_type": ContentType,
        "date": date,
        "query": {"Action": action, "Version": Version, **query},
    }
    if body is None:
        request_param["body"] = ""
    x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])
    request_param["body"] = request_param["body"].encode("utf-8")
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }
    signed_headers_str = ";".join(
        ["content-type", "host", "x-content-sha256", "x-date"]
    )
    canonical_request_str = "\n".join(
        [request_param["method"].upper(),
         request_param["path"],
         norm_query(request_param["query"]),
         "\n".join(
             [
                 "content-type:" + request_param["content_type"],
                 "host:" + request_param["host"],
                 "x-content-sha256:" + x_content_sha256,
                 "x-date:" + x_date,
             ]
         ),
         "",
         signed_headers_str,
         x_content_sha256,
         ]
    )

    # print(canonical_request_str)
    hashed_canonical_request = hash_sha256(canonical_request_str)

    # print(hashed_canonical_request)
    # print("-----------------------------------------------------------------------------")
    credential_scope = "/".join([short_x_date, credential["region"], credential["service"], "request"])
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])

    # 打印最终计算的签名字符串用于调试比对
    # print(string_to_sign)
    # print("-----------------------------------------------------------------------------")
    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    sign_result["Authorization"] = "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
        credential["access_key_id"] + "/" + credential_scope,
        signed_headers_str,
        signature,
    )
    header = {**header, **sign_result}
    # header = {**header, **{"X-Security-Token": SessionToken}}
    # 第六步：将 Signature 签名写入 HTTP Header 中，并发送 HTTP 请求。
    print("https://{}{}".format(request_param["host"], request_param["path"]))
    r = requests.request(method=method,
                         url="https://{}{}".format(request_param["host"], request_param["path"]),
                         headers=header,
                         params=request_param["query"],
                         data=request_param["body"],
                         )
    return r.json()

def aifig(user_id,is_group,group_id,message,user_name):
    now = datetime.datetime.utcnow()
    message[1] = message[1].replace("\n", "")
    message[1] = message[1].replace("\r", "")
    # message = re.sub(r"[\r\n]+", "", message)
    response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"high_aes_general_v30l_zt2i","prompt":"'+message[1]+'"}')
    if(response_body["code"] == 50511):
        return "生成的图片没过审核"
    elif(response_body["code"] == 50412):
        return "输入的文字没过审核"
    elif(response_body["code"] == 10000):
        image_data = base64.b64decode(response_body["data"]["binary_data_base64"][0])
        image = Image.open(BytesIO(image_data))
        file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
        send.sendImg(user_id,is_group,group_id,file_path)
        return ""
    else:
        return "你可以告诉笨比银风是"+str(response_body["code"])+"的错误码，但估计他也解决不了"
    
def aifig2(user_id,is_group,group_id,message,user_name,url):
    now = datetime.datetime.utcnow()
    message = message.replace("\n", "")
    message = message.replace("\r", "")
    response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"seededit_v3.0","image_urls":["'+url+'"],"prompt":"'+message+'"}')
    # response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"i2i_portrait_photo","image_input":"'+url+'","prompt":"'+message+'"}')
    if(response_body["code"] == 50511):
        return "生成的图片没过审核"
    elif(response_body["code"] == 50412):
        return "输入的文字没过审核"
    elif(response_body["code"] == 50413):
        return "输入文本含敏感词、版权词等审核不通过"
    elif(response_body["code"] == 10000):
        image_data = base64.b64decode(response_body["data"]["binary_data_base64"][0])
        image = Image.open(BytesIO(image_data))
        file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
        send.sendImg(user_id,is_group,group_id,file_path)
        return ""
    else:
        return "你可以告诉笨比银风是"+str(response_body["code"])+"的错误码，但估计他也解决不了"

def aifig3(user_id,is_group,group_id,message,user_name,url):
    now = datetime.datetime.utcnow()
    message = message.replace("\n", "")
    message = message.replace("\r", "")
    response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"jimeng_i2i_v30","image_urls":["'+url+'"],"prompt":"'+message+'"}')
    # response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"i2i_portrait_photo","image_input":"'+url+'","prompt":"'+message+'"}')
    if(response_body["code"] == 50511):
        return "生成的图片没过审核"
    elif(response_body["code"] == 50412):
        return "输入的文字没过审核"
    elif(response_body["code"] == 50413):
        return "输入文本含敏感词、版权词等审核不通过"
    elif(response_body["code"] == 10000):
        image_data = base64.b64decode(response_body["data"]["binary_data_base64"][0])
        image = Image.open(BytesIO(image_data))
        file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
        send.sendImg(user_id,is_group,group_id,file_path)
        return ""
    else:
        return "你可以告诉笨比银风是"+str(response_body["code"])+"的错误码，但估计他也解决不了"
    
def aifig4(user_id,is_group,group_id,message,user_name,url):
    now = datetime.datetime.utcnow()
    message = message.replace("\n", "")
    message = message.replace("\r", "")
    response_body = request("POST", now, {}, {}, AK, SK, "CVProcess", '{"req_key":"i2i_outpainting","image_urls":["'+url+'"],"prompt":"'+message+'","top":0.5,"bottom":0.5,"left":0.5,"right":0.5}')
    if(response_body["code"] == 50511):
        return "生成的图片没过审核"
    elif(response_body["code"] == 50412):
        return "输入的文字没过审核"
    elif(response_body["code"] == 50413):
        return "输入文本含敏感词、版权词等审核不通过"
    elif(response_body["code"] == 10000):
        image_data = base64.b64decode(response_body["data"]["binary_data_base64"][0])
        image = Image.open(BytesIO(image_data))
        file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
        send.sendImg(user_id,is_group,group_id,file_path)
        return ""
    else:
        return "你可以告诉笨比银风是"+str(response_body["code"])+"的错误码，但估计他也解决不了"