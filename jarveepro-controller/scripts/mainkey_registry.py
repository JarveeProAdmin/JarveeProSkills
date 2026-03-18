"""Mapping of Platform+TaskType to preferred mainKey values."""
from __future__ import annotations

MAINKEY_MAP = {
    "Facebook": {
        "AddBioInformation": ["Text"],
        "ChangeName": ["Text"],
        "ChangeProfileName": ["Text"],
        "ChangeCoverPhoto": ["PhotoPath"],
        "ChangeProfilePicture": ["PhotoPath"],
        "Comment": ["Text", "PhotoPath"],
        "ReplayComment": ["Text", "PhotoPath"],
        "NewPost": ["PhotoPath", "VideoPath", "Text"],
        "PostToGroup": ["PhotoPath", "VideoPath", "Text"],
        "PostToPage": ["PhotoPath", "VideoPath", "Text"],
        "SendMessage": ["Text"],
    },
    "Instagram": {
        "ChangeName": ["Text"],
        "ChangeUsername": ["Text"],
        "ChangeProfilePicture": ["PhotoPath"],
        "Comment": ["Text"],
        "ReplyComment": ["Text"],
        "Post": ["PhotoPath", "VideoPath"],
        "SendMessage": ["Text", "PhotoPath", "VideoPath"],
    },
    "Tiktok": {
        "Comment": ["Text"],
        "Post": ["VideoPath"],
        "SearchLive": ["SearchText"],
        "SearchLiveUser": ["SearchText"],
        "SearchPeople": ["SearchText"],
        "SerarchVideo": ["SearchText"],
        "SerarchVideoUser": ["SearchText"],
        "SendMessage": ["Text"],
    },
    "Twitter": {
        "AddWebsite": ["Text"],
        "ChangeProfileName": ["Text"],
        "ChangeUsername": ["Text"],
        "ChangeBirthDate": ["Text"],
        "SendMessage": ["Text", "PhotoPath", "VideoPath"],
        "SetupProfile": ["PhotoPath", "SubPhotoPath", "Text", "SubText"],
        "Tweet": ["PhotoPath", "VideoPath", "Text"],
    },
    "Youtube": {
        "ChangeProfileName": ["Text"],
        "Comment": ["Text"],
        "ReplyComment": ["Text"],
        "UploadVideo": ["VideoPath"],
    },
}


def resolve_mainkey(platform: str | None, task_type: str | None) -> list[str] | None:
    if not platform or not task_type:
        return None
    return MAINKEY_MAP.get(platform, {}).get(task_type)


__all__ = ["MAINKEY_MAP", "resolve_mainkey"]
