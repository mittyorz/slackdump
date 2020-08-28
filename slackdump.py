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
    if not res.ok:
        if "Retry-After" in res.headers:
            sec = int(res.headers["Retry-After"]) + 10
            print(" ", url, " : rate limit exceeded, waiting ", sec, "seconds ", end="", flush=True)
            time.sleep(sec)
            return requestBody(url,param)
        raise RuntimeError(res.text)
    j=res.json()
    if not j["ok"]: raise RuntimeError(j["error"])
    return j


def GetUsersListRequestParam(token):
    return {
        'token' : token,
        #'cursor' : '',
        'include_locale' : False,
        'limit' : 0
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
        'limit' : 100
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
    print("retrieving users list .", end="", flush=True)
    param=GetUsersListRequestParam(token)
    _users=GetUsersList(param)
    users=copy.deepcopy(_users)
    while _users["response_metadata"]["next_cursor"]:
        print(".", end="", flush=True)
        param["cursor"] = _users["response_metadata"]["next_cursor"]
        _users = GetUsersList(param)
        users["members"]+=_users["members"]
    if "response_metadata" in users: del users["response_metadata"]
    print(" done", flush=True)

    print("retrieving channels list .", end="", flush=True)
    param=GetConversationsListRequestParam(token)
    _ochannels=GetConversationsList(param)
    ochannels=copy.deepcopy(_ochannels)
    while _ochannels["response_metadata"]["next_cursor"]:
        print(".", end="", flush=True)
        param["cursor"] = _ochannels["response_metadata"]["next_cursor"]
        _ochannels=GetConversationsList(param)
        ochannels["channels"]+=_ochannels["channels"]
    print(" done", flush=True)

    #filter channls by channel names
    if channel_names[0]=="*": channels=copy.deepcopy(ochannels)
    else: channels=[x for x in ochannels["channels"] if x["name"] in channel_names]

    #get messages and their replies
    channel_users = {}
    for ch in channels:
        print("retrieving conversation's history .", end="", flush=True)
        param = GetConversationsHistoryRequestParam(token,ch["id"])
        param["limit"]=1000
        if latest_ts!='now': param["latest"]=latest_ts
        if oldest_ts!='0': param["oldest"]=oldest_ts
        _history = GetConversationsHistory(param)
        history=copy.deepcopy(_history)
        #TODO: next_cursor
        while _history["has_more"]:
            print(".", end="", flush=True)
            param["cursor"] = _history["response_metadata"]["next_cursor"]
            _history = GetConversationsHistory(param)
            history["messages"]+=_history["messages"]
        history["has_more"]=False
        if "response_metadata" in history: del history["response_metadata"]
        print(" done", flush=True)

        #50 limits per minute に引っかかりそう
        #適当に待った方がいいかも
        print("retrieving thread of messages ", end="", flush=True)
        for msg in history["messages"]:
            if "user" in msg:
                for u in users["members"]:
                    if msg["user"] == u["id"]:
                        channel_users[msg["user"]] = u
            if "thread_ts" in msg:
                print(".", end="", flush=True)
                param=GetConversationsRepliesRequestParam(token,ch["id"],msg["ts"])
                param["limit"]=10
                _replies=GetConversationsReplies(param)
                replies=copy.deepcopy(_replies)
                time.sleep(1)   # rate limit of conversations.replies is 50+ per minute
                while _replies["has_more"]:
                    print("+", end="", flush=True)
                    param["cursor"] = _replies["response_metadata"]["next_cursor"]
                    _replies = GetConversationsReplies(param)
                    replies["messages"]+=_replies["messages"]
                    time.sleep(1)   # rate limit of conversations.replies is 50+ per minute
                replies["has_more"]=False
                if "response_metadata" in replies: del replies["response_metadata"]
                replies["messages"]=[x for x in replies["messages"] if x["thread_ts"] != x["ts"]]
                msg["replies_body"]=replies
        print(" done", flush=True)
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
