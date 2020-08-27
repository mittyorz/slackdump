'''
Dump slack history using Slack Conversation API.
(c) 2019 Ryota Suzuki. All rights reserved.
See LICENCE for details.
'''
import requests
import os,sys,re
import json
import argparse
import copy
import time

BASE_URL='https://slack.com/api/'

def requestBody(url,param):
    res=requests.get(url,param)
    res.encoding = res.apparent_encoding
    if not res.ok: raise RuntimeError(res.text)
    j=res.json()
    if not j["ok"]: raise RuntimeError(j["error"])
    return j


def GetUsersListRequestParam(token):
    return {
        'token' : token,
        #'cursor' : '',
        'include_locale' : False,
        'limits' : 0
    }
def GetUsersList(param):
    return requestBody(BASE_URL+'users.list',param)

def GetConversationsHistoryRequestParam(token,id):
    return {
        'token' : token,
        'channel' : id,
        #'cursor' : '',
        'inclusive' : False,
        #'latest' : 'now',
        #'oldest' : '0',
        'limits' : 100
    }
def GetConversationsHistory(param):
    return requestBody(BASE_URL+'conversations.history',param)

def GetConversationsInfoRequestParam(token,id):
    return {
        'token' : token,
        'channel' : id
    }
def GetConversationsInfo(param):
    return requestBody(BASE_URL+'conversations.info',param)

def GetConversationsRepliesRequestParam(token,id,ts):
    return {
        'token' : token,
        'channel' : id,
        'ts' : ts,
        #'cursor' : '',
        'inclusive' : False,
        #'latest' : 'now',
        #'oldest' : '0',
        'limit' : 10
    }
def GetConversationsReplies(param):
    return requestBody(BASE_URL+'conversations.replies',param)

def GetConversationsListRequestParam(token):
    return {
        'token' : token,
        #'cursor' : '',
        'exclude_archived' : True,
        'limit' : 100,
        'types' : 'public_channel,private_channel'
    }
def GetConversationsList(param):
    return requestBody(BASE_URL+'conversations.list',param)


def main():
    aparser=argparse.ArgumentParser(description="Dump slack history using Slack Conversation API. Only channels to which you belong are dumped. [NOTICE] Be cadeful for fetching limit")
    aparser.add_argument("-t", "--token", help="access token")
    aparser.add_argument("--since", default="0", help="start time stamp")
    aparser.add_argument("--until", default="now", help="end time stamp")
    aparser.add_argument("channel_names", nargs="*", help="channel names to dump. * for dump all channels")
    args=aparser.parse_args()
    token = args.token
    channel_names = args.channel_names
    oldest_ts = args.since
    latest_ts = args.until

    #
    param=GetUsersListRequestParam(token)
    _users=GetUsersList(param)
    users=copy.deepcopy(_users)
    while _users["response_metadata"]["next_cursor"]:
        param["cursor"] = _users["response_metadata"]["next_cursor"]
        _users = GetUsersList(param)
        users["members"]+=_users["members"]
        time.sleep(3)   # rate limit of users.list is 20+ per minute
    if "response_metadata" in users: del users["response_metadata"]

    param=GetConversationsListRequestParam(token)
    _ochannels=GetConversationsList(param)
    ochannels=copy.deepcopy(_ochannels)
    while _ochannels["response_metadata"]["next_cursor"]:
        param["cursor"] = _ochannels["response_metadata"]["next_cursor"]
        _ochannels=GetConversationsList(param)
        ochannels["channels"]+=_ochannels["channels"]
        time.sleep(3)   # rate limit of conversations.list is 20+ per minute

    #filter channls by channel names
    if channel_names[0]=="*": channels=copy.deepcopy(ochannels)
    else: channels=[x for x in ochannels["channels"] if x["name"] in channel_names]

    #get messages and their replies
    channel_users = {}
    for ch in channels:
        param = GetConversationsHistoryRequestParam(token,ch["id"])
        param["limits"]=1000
        if latest_ts!='now': param["latest"]=latest_ts
        if oldest_ts!='0': param["oldest"]=oldest_ts
        _history = GetConversationsHistory(param)
        history=copy.deepcopy(_history)
        #TODO: next_cursor
        while _history["has_more"]:
            param["cursor"] = _history["response_metadata"]["next_cursor"]
            _history = GetConversationsHistory(param)
            history["messages"]+=_history["messages"]
            time.sleep(1)   # rate limit of conversations.history is 50+ per minute
        history["has_more"]=False
        if "response_metadata" in history: del history["response_metadata"]

        #50 limits per minute に引っかかりそう
        #適当に待った方がいいかも
        for msg in history["messages"]:
            if "user" in msg:
                for u in users["members"]:
                    if msg["user"] == u["id"]:
                        channel_users[msg["user"]] = u
            if "thread_ts" in msg:
                param=GetConversationsRepliesRequestParam(token,ch["id"],msg["ts"])
                param["limits"]=1000
                _replies=GetConversationsReplies(param)
                replies=copy.deepcopy(_replies)
                while _replies["has_more"]:
                    param["cursor"] = _replies["response_metadata"]["next_cursor"]
                    _replies = GetConversationsReplies(param)
                    replies["messages"]+=_replies["messages"]
                    time.sleep(1)   # rate limit of conversations.replies is 50+ per minute
                replies["has_more"]=False
                if "response_metadata" in replies: del replies["response_metadata"]
                replies["messages"]=[x for x in replies["messages"] if x["thread_ts"] != x["ts"]]
                msg["replies_body"]=replies
        ch["history"]=history

    #save
    with open("users.json","w",encoding="utf8") as fp:
        json.dump(users,fp,ensure_ascii=False,indent=4)
    with open("channels.json","w",encoding="utf8") as fp:
        json.dump(channels,fp,ensure_ascii=False,indent=4)
    with open("channel-users.json","w",encoding="utf8") as fp:
        json.dump(channel_users,fp,ensure_ascii=False,indent=4)

if __name__ == "__main__":
    main()
