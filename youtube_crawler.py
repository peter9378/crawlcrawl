import requests
import json
import time
import traceback


class Youtube:
    def __init__(self):
        self.click_tracking_params = ""
        self.continuation_command = ""
        self.api_key = ""
        self.post_json = {
            "continuation": "",
            "context": {},
        }

        self.detail_json = {
            "contentCheckOk": False,
            "context": {},
            # 넣기
            "params": "",
            "playbackContext": {
                "contentPlaybackContext": {
                    "autoCaptionsDefaultOn": False,
                    "autonav": False,
                    "autonavState": "STATE_NONE",
                    "autoplay": True,
                    # 넣기
                    "currentUrl": "",
                    "html5Preference": "HTML5_PREF_WANTS",
                    "lactMilliseconds": "-1",
                    # 넣기
                    "referer": "",
                    "signatureTimestamp": 19590,
                    "splay": False,
                    "vis": 5,
                },
                "watchAmbientModeContext": {
                    "hasShownAmbientMode": True,
                    "watchAmbientModeEnabled": True,
                },
            },
            "racyCheckOk": False,
            # 넣기
            "videoId": "",
        }

    def get_info_by_keyword(self, keyword: str, limit: int, sleep_sec: float = 1.5):
        try:
            # first page api 요청
            res = self._api_search_page(keyword=keyword)

            # api key 가져오기
            api_key_raw_start = res.find("INNERTUBE_API_KEY")
            api_key_raw = res[api_key_raw_start : api_key_raw_start + 130]
            startPoint = api_key_raw.find(":")
            endPoint = api_key_raw.find(",")
            self.api_key = api_key_raw[startPoint + 2 : endPoint - 1]

            # 설정파일 만들기.
            startPoint = res.find("INNERTUBE_CONTEXT") + 2 + len("INNERTUBE_CONTEXT")
            endPoint = res.find("INNERTUBE_CONTEXT_CLIENT_NAME") - 2
            config_data_raw = res[startPoint:endPoint]
            config_data = json.loads(config_data_raw)
            # context에 넣기
            self.post_json["context"] = config_data
            self.detail_json["context"] = config_data
            # 결과 json으로 변형
            initial_data = res.split("ytInitialData = ")[1]
            splited = initial_data.split(";</script>")
            initial_data_json_raw = splited[0]
            initial_data_json = json.loads(initial_data_json_raw)

            # 다음 페이지 정보 가져오기
            try:
                next_page_info_json = initial_data_json["contents"][
                    "twoColumnSearchResultsRenderer"
                ]["primaryContents"]["sectionListRenderer"]["contents"][1][
                    "continuationItemRenderer"
                ]
            except:
                next_page_info_json = {}

            # 값 넣어주기
            is_break = False
            try:
                self.click_tracking_params = next_page_info_json[
                    "continuationEndpoint"
                ]["clickTrackingParams"]
                self.continuation_command = next_page_info_json["continuationEndpoint"][
                    "continuationCommand"
                ]["token"]
                self.post_json["continuation"] = self.continuation_command
            except:
                self.click_tracking_params = ""
                self.continuation_command = ""
                is_break = True

            # 데이터 가공
            youtube_list_json = initial_data_json["contents"][
                "twoColumnSearchResultsRenderer"
            ]["primaryContents"]["sectionListRenderer"]["contents"][0][
                "itemSectionRenderer"
            ][
                "contents"
            ]

            # 유튜브 리스트 json 저장
            with open("youtube_list.json", 'w') as json_file:
                json.dump(youtube_list_json, json_file, ensure_ascii=False, indent=4)

            # 결과 초기화
            result = []
            limit_count = limit

            """
            상세페이지 반복
            """

            for detail in youtube_list_json:
                if "videoRenderer" not in detail:
                    if "reelShelfRenderer" not in detail:
                        continue

                if limit_count == 0:
                    break
                time.sleep(sleep_sec)
                try:
                    self.detail_json["context"]["clickTracking"][
                        "clickTrackingParams"
                    ] = detail["videoRenderer"]["navigationEndpoint"][
                        "clickTrackingParams"
                    ]
                    self.detail_json["videoId"] = detail["videoRenderer"]["videoId"]

                    self.detail_json["params"] = detail["videoRenderer"][
                        "navigationEndpoint"
                    ]["watchEndpoint"]["playerParams"]

                    self.detail_json["playbackContext"]["contentPlaybackContext"][
                        "currentUrl"
                    ] = detail["videoRenderer"]["navigationEndpoint"][
                        "commandMetadata"
                    ][
                        "webCommandMetadata"
                    ][
                        "url"
                    ]

                    self.detail_json["playbackContext"]["contentPlaybackContext"][
                        "referer"
                    ] = f"https://www.youtube.com/results?search_query={keyword}"

                    response = self._api_detail_page(self.api_key)
                    
                    # comment
                    comment_response = self._api_detail_comment(self.api_key)
                    token = comment_response['contents']['twoColumnWatchNextResults']['results']['results']['contents'][3]['itemSectionRenderer']['contents'][0]['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
                    self.comment_json = {
                        'context':self.detail_json['context'],
                        'continuation':token
                    }
                    comments_res = self._api_comments(self.api_key)
                    comment_limit = 10
                    comment_count = len(comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'])
                    if comment_count<=10:
                        comment_limit = comment_count
                    comments = []
                    for i in range(0, comment_limit):
                        comment = comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'][i]['commentThreadRenderer']['comment']['commentRenderer']
                        author = comment['authorText']['simpleText']
                        text = comment['contentText']['runs'][0]['text']
                        comments.append({
                            'author':author,
                            'text':text,
                        })
                    result.append(
                        {
                            "VideoID": self.detail_json["videoId"],
                            "title": response["videoDetails"]["title"],
                            "description": response["videoDetails"][
                                "shortDescription"
                            ],
                            "viewCount": response["videoDetails"]["viewCount"],
                            "author": response["videoDetails"]["author"],
                            "publishDate": response["microformat"][
                                "playerMicroformatRenderer"
                            ]["publishDate"],
                            "comments":{
                                "count":comments_res['onResponseReceivedEndpoints'][0]['reloadContinuationItemsCommand']['continuationItems'][0]['commentsHeaderRenderer']['countText']['runs'][1]['text'],
                                "comments":comments
                            }
                        }
                    )
                    print(result[-1])

                except:
                    self.detail_items = detail["reelShelfRenderer"]["items"]
                    for item in self.detail_items:
                        try:
                            self.detail_json["context"]["clickTracking"][
                                "clickTrackingParams"
                            ] = item["reelItemRenderer"]["navigationEndpoint"][
                                "clickTrackingParams"
                            ]
                            self.detail_json["videoId"] = item["reelItemRenderer"]["videoId"]

                            self.detail_json["params"] = item["reelItemRenderer"][
                                "navigationEndpoint"
                            ][
                                "reelWatchEndpoint"
                                ]["playerParams"]

                            self.detail_json["playbackContext"]["contentPlaybackContext"][
                                "currentUrl"
                            ] = item["reelItemRenderer"]["navigationEndpoint"][
                                "commandMetadata"
                            ][
                                "webCommandMetadata"
                            ][
                                "url"
                            ]

                            self.detail_json["playbackContext"]["contentPlaybackContext"][
                                "referer"
                            ] = f"https://www.youtube.com/results?search_query={keyword}"

                            response = self._api_detail_page(self.api_key)
                            
                            # comment
                            comment_response = self._api_detail_comment(self.api_key)
                            token = comment_response['contents']['twoColumnWatchNextResults']['results']['results']['contents'][3]['itemSectionRenderer']['contents'][0]['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
                            self.comment_json = {
                                'context':self.detail_json['context'],
                                'continuation':token
                            }
                            comments_res = self._api_comments(self.api_key)
                            comment_limit = 10
                            try:
                                comment_count = len(comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'])
                                if comment_count<=10:
                                    comment_limit = comment_count
                            except:
                                comment_count = 0
                                comment_limit = 0
                            comments = []
                            for i in range(0, comment_limit):
                                try:
                                    comment = comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'][i]['commentThreadRenderer']['comment']['commentRenderer']
                                    author = comment['authorText']['simpleText']
                                    text = comment['contentText']['runs'][0]['text']
                                    comments.append({
                                        'author':author,
                                        'text':text,
                                    })
                                except Exception as e:
                                    print(e)
                                    continue
                            if comment_count != 0:
                                result.append(
                                    {
                                        "VideoID": self.detail_json["videoId"],
                                        "title": f'#shorts {response["videoDetails"]["title"]}',
                                        "description": f'#shorts {response["videoDetails"]["shortDescription"]}',
                                        "viewCount": 0,
                                        "author": response["videoDetails"][
                                            "author"
                                            ],
                                        "publishDate": response["microformat"][
                                            "playerMicroformatRenderer"
                                        ]["publishDate"],
                                        "comments":{
                                            "count":comments_res['onResponseReceivedEndpoints'][0]['reloadContinuationItemsCommand']['continuationItems'][0]['commentsHeaderRenderer']['countText']['runs'][1]['text'],
                                            "comments":comments
                                        }
                                    }
                                )
                            else:
                                result.append(
                                    {
                                        "VideoID": self.detail_json["videoId"],
                                        "title": f'#shorts {response["videoDetails"]["title"]}',
                                        "description": f'#shorts {response["videoDetails"]["shortDescription"]}',
                                        "viewCount": 0,
                                        "author": response["videoDetails"][
                                            "author"
                                            ],
                                        "publishDate": response["microformat"][
                                            "playerMicroformatRenderer"
                                        ]["publishDate"],
                                        "comments":{
                                            "count":0,
                                            "comments":comments
                                        }
                                    }
                                )
                            print(result[-1])
                        except Exception as e:
                            print(e)
                            traceback.print_exc()
                            continue

                limit_count -= 1

            while limit_count > 0 and is_break == False:
                time.sleep(sleep_sec)

                # 다음 페이지 가져오기
                initial_data_json = self._api_search_page_next(self.api_key)

                # 다음 페이지를 위한 파라메터 저장

                try:
                    self.click_tracking_params = initial_data_json[
                        "onResponseReceivedCommands"
                    ][0]["clickTrackingParams"]

                    self.continuation_command = initial_data_json[
                        "onResponseReceivedCommands"
                    ][0]["appendContinuationItemsAction"]["continuationItems"][1][
                        "continuationItemRenderer"
                    ][
                        "continuationEndpoint"
                    ][
                        "continuationCommand"
                    ][
                        "token"
                    ]

                    self.post_json["continuation"] = self.continuation_command
                except:
                    break

                # 데이터 가져오기
                youtube_list_json = initial_data_json["onResponseReceivedCommands"][0][
                    "appendContinuationItemsAction"
                ]["continuationItems"][0]["itemSectionRenderer"]["contents"]

                for detail in youtube_list_json:
                    if "videoRenderer" not in detail:
                        continue

                    if limit_count == 0:
                        break

                    time.sleep(sleep_sec)

                    try:
                        self.detail_json["context"]["clickTracking"][
                            "clickTrackingParams"
                        ] = detail["videoRenderer"]["navigationEndpoint"][
                            "clickTrackingParams"
                        ]

                        self.detail_json["videoId"] = detail["videoRenderer"]["videoId"]

                        self.detail_json["params"] = detail["videoRenderer"][
                            "navigationEndpoint"
                        ]["watchEndpoint"]["playerParams"]

                        self.detail_json["playbackContext"]["contentPlaybackContext"][
                            "currentUrl"
                        ] = detail["videoRenderer"]["navigationEndpoint"][
                            "commandMetadata"
                        ][
                            "webCommandMetadata"
                        ][
                            "url"
                        ]

                        self.detail_json["playbackContext"]["contentPlaybackContext"][
                            "referer"
                        ] = f"https://www.youtube.com/results?search_query={keyword}"

                        response = self._api_detail_page(self.api_key)

                        comment_response = self._api_detail_comment(self.api_key)
                        token = comment_response['contents']['twoColumnWatchNextResults']['results']['results']['contents'][3]['itemSectionRenderer']['contents'][0]['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
                        self.comment_json = {
                            'context':self.detail_json['context'],
                            'continuation':token
                        }
                        comments_res = self._api_comments(self.api_key)
                        comment_limit = 10
                        comment_count = len(comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'])
                        if comment_count<=10:
                            comment_limit = comment_count
                        comments = []
                        for i in range(0, comment_limit):
                            comment = comments_res['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems'][i]['commentThreadRenderer']['comment']['commentRenderer']
                            author = comment['authorText']['simpleText']
                            text = comment['contentText']['runs'][0]['text']
                            comments.append({
                                'author':author,
                                'text':text,
                            })
                        result.append(
                            {
                                "VideoID": self.detail_json["videoId"],
                                "title": response["videoDetails"]["title"],
                                "description": response["videoDetails"][
                                    "shortDescription"
                                ],
                                "viewCount": response["videoDetails"]["viewCount"],
                                "author": response["videoDetails"]["author"],
                                "publishDate": response["microformat"][
                                    "playerMicroformatRenderer"
                                ]["publishDate"],
                                "comments":{
                                    "count":comments_res['onResponseReceivedEndpoints'][0]['reloadContinuationItemsCommand']['continuationItems'][0]['commentsHeaderRenderer']['countText']['runs'][1]['text'],
                                    "comments":comments
                                }
                            }
                        )
                        print(result)

                    except:
                        continue

                    limit_count -= 1


        except Exception as e:
            print(e)
        return result


    def _api_search_page(self, keyword: str):
        try:
            res = requests.get(
                f"https://www.youtube.com/results?search_query={keyword}",
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "content-type": "text/html; charset=utf-8",
                },
            )

            if res.status_code != 200:
                raise Exception("stauts code error")
            
            return res.content.decode("utf-8")
        except:
            raise Exception("api 실패")

    def _api_detail_page(self, key):
        try:
            session = requests.Session()
            session.cookies.clear()
            res = session.post(
                f"https://www.youtube.com/youtubei/v1/player?key={key}&prettyPrint=false",
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "content-type": "application/json; charset=UTF-8",
                },
                json=self.detail_json,
            )

            if res.status_code != 200:
                raise Exception("stauts code error")

            return json.loads(res.content)
        except:
            raise Exception("api 실패")

    def _api_search_page_next(self, key: str):
        try:
            session = requests.Session()
            session.cookies.clear()
            res = session.post(
                f"https://www.youtube.com/youtubei/v1/search?key={key}&prettyPrint=false",
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "content-type": "application/json; charset=UTF-8",
                },
                json=self.post_json,
            )

            if res.status_code != 200:
                raise Exception("stauts code error")

            return json.loads(res.content)
        except:
            raise Exception("api 실패")
        
    def _api_detail_comment(self, key:str):
        try:
            session = requests.Session()
            session.cookies.clear()
            res = session.post(
                # f"https://www.youtube.com/youtubei/v1/player?key={key}&prettyPrint=false",
                f"https://www.youtube.com/youtubei/v1/next?key={key}&prettyPrint=false",
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "content-type": "application/json; charset=UTF-8",
                },
                json=self.detail_json,
            )

            if res.status_code != 200:
                raise Exception("stauts code error")

            return json.loads(res.content)
        except:
            raise Exception("api 실패")
        
    def _api_comments(self, key:str):
        try:
            session = requests.Session()
            session.cookies.clear()
            res = session.post(
                f"https://www.youtube.com/youtubei/v1/next?key={key}&prettyPrint=false",
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                    "accept-language": "ko-KR,ko;q=0.9",
                    "content-type": "application/json; charset=UTF-8",
                },
                json=self.comment_json,
            )

            if res.status_code != 200:
                raise Exception("status code error")

            return json.loads(res.content)
        except:
            raise Exception("api 실패")
