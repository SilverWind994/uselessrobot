from PIL import Image

def SavePhoto(user_id,is_group,group_id,photo):
    file_path = getPhotoPath(user_id,is_group,group_id)
    photo.save(file_path)
    return file_path

def getPhotoPath(user_id,is_group,group_id):

    if(is_group):
        file_path = "C:\\mybot\\photoFile\\g_"+str(group_id)+".png"
    else:
        file_path = "C:\\mybot\\photoFile\\p_"+str(user_id)+".png"
    return file_path