import json
import os

def GetJson(user_id,is_group,group_id):
    file_path = GetJsonPath(user_id,is_group,group_id)

    if(not os.path.exists(file_path)):
        return ResetJson(user_id,is_group,group_id)
    with open(file_path, "r") as file:
        status_data = json.load(file)
    return status_data

def ResetJson(user_id,is_group,group_id):
    file_path = GetJsonPath(user_id,is_group,group_id)

    status_data = {"status":"none","data":{},"group_bind":False}
    with open(file_path, "w") as file:
        json.dump(status_data, file)
    return status_data

def SetJson(user_id,is_group,group_id,data):
    file_path = GetJsonPath(user_id,is_group,group_id)

    with open(file_path, "w") as file:
        json.dump(data, file)

    return

def GetJsonPath(user_id,is_group,group_id):
    if(is_group):
        file_path = "C:\\mybot\\jsonFile\\g_"+str(group_id)+".json"
    else:
        file_path = "C:\\mybot\\jsonFile\\p_"+str(user_id)+".json"
    return file_path