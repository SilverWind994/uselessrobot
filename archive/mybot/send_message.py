import requests
import random
def sendTextToGroupWithAt(group_id,user_id,message):
    requests.post('http://localhost:3000/send_group_msg', json={
            'group_id': group_id,
            'message': [{
                'type': 'at',
                'data': {
                    'qq': user_id
                }
            },
            {
                'type': 'text',
                'data': {
                    'text': " "+message
                }
            }]
        })

def sendTextBack(data,message):
    if(message==""):
        return
    if(data["message_type"]=="group"):
        sendTextToGroup(data["group_id"],message)
    if(data["message_type"]=="private"):
        sendTextToPrivate(data["user_id"],message)
    return

def sendText(user_id,is_group,group_id,message):
    if(is_group):
        sendTextToGroup(group_id,message)
    else:
        sendTextToPrivate(user_id,message)
    return

def sendTextToGroup(group_id,message):
    requests.post('http://localhost:3000/send_group_msg', json={
        'group_id': group_id,
        'message': [{
            'type': 'text',
            'data': {
                'text': message
            }
        }]
    })

def sendTextToPrivate(user_id,message):
    requests.post('http://localhost:3000/send_private_msg', json={
            'user_id': user_id,
            'message': [{
                'type': 'text',
                'data': {
                    'text': message
                }
            }]
        })
    return

def sendImgBack(data,message):
    if(message==""):
        return
    if(data["message_type"]=="group"):
        sendImgToGroup(data["group_id"],message)
    if(data["message_type"]=="private"):
        sendImgToPrivate(data["user_id"],message)
    return

def sendImg(user_id,is_group,group_id,message):
    if(is_group):
        sendImgToGroup(group_id,message)
    else:
        sendImgToPrivate(user_id,message)
    return

def sendImgToGroup(group_id,message):
    requests.post('http://localhost:3000/send_group_msg', json={
            'group_id': group_id,
            'message': [{
                'type': 'image',
                'data': {
                    'file': message
                }
            }]
        })
    return

def sendImgToPrivate(user_id,message):
    requests.post('http://localhost:3000/send_private_msg', json={
            'user_id': user_id,
            'message': [{
                'type': 'image',
                'data': {
                    'file': message
                }
            }]
        })
    return

def sendVideo(user_id,is_group,group_id,message):
    if(is_group):
        sendVideoToGroup(group_id,message)
    else:
        sendVideoToPrivate(user_id,message)
    return

def sendVideoToGroup(group_id,message):
    requests.post('http://localhost:3000/send_group_msg', json={
            'group_id': group_id,
            'message': [{
                'type': 'video',
                'data': {
                    'file': message
                }
            }]
        })
    return

def sendVideoToPrivate(user_id,message):
    requests.post('http://localhost:3000/send_private_msg', json={
            'user_id': user_id,
            'message': [{
                'type': 'video',
                'data': {
                    'file': message
                }
            }]
        })
    return

def getGroupMembers(group_id):
    msg = requests.post('http://localhost:3000/get_group_member_list', json={
            'group_id': group_id,
            "no_cache": True
        })
    return msg

def sendPokeToPrivate(user_id):
    print(9876544321)
    a = requests.post('http://localhost:3000/friend_poke', json={
           'user_id': user_id
       })
    return
 
def sendPokeToGroup(user_id,group_id):
    print(123456789)
    a = requests.post('http://localhost:3000/group_poke', json={
           "group_id": group_id,
           "user_id": user_id
        })
    return


def sendVoiceBack(data,message):
    if(message==""):
        return
    if(data["message_type"]=="group"):
        sendVoiceToGroup(data["group_id"],message)
    if(data["message_type"]=="private"):
        sendVoiceToPrivate(data["user_id"],message)
    return

def sendVoice(user_id,is_group,group_id,message):
    if(is_group):
        sendVoiceToGroup(group_id,message)
    else:
        sendVoiceToPrivate(user_id,message)
    return

def sendVoiceToGroup(group_id,message):
    requests.post('http://localhost:3000/send_group_msg', json={
        'group_id': group_id,
        'message': [{
            'type': 'record',
            'data': {
                'file': message
            }
        }]
    })

def sendVoiceToPrivate(user_id,message):
    requests.post('http://localhost:3000/send_private_msg', json={
            'user_id': user_id,
            'message': [{
                'type': 'record',
                'data': {
                    'file': message
                }
            }]
        })
    return