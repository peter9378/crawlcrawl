import sys
import json
import requests
import traceback

from bs4 import BeautifulSoup
import logging

class Scraper:
    def __init__(self):
        self.keyword = ""
        self.click_tracking_params = ""
        self.continuation_command = ""
        self.api_key = ""
        self.post_json = {
            "continuation": "",
            "context": {},
        }
        self.result = []
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
        self.logger = logging.getLogger('uvicorn')
    def _api_search_page(self, keyword: str):
            self.detail_json["playbackContext"]["contentPlaybackContext"][
                "referer"
            ] = f"https://www.youtube.com/results?search_query={keyword}"
            self.keyword = keyword
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
                # raise Exception("api 실패")
                self._api_search_page(keyword=keyword)

    def first_page_setting(self, keyword: str):
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
            next_page_info_contents = initial_data_json["contents"][
                "twoColumnSearchResultsRenderer"
            ]["primaryContents"]["sectionListRenderer"]["contents"]
            try:
                next_page_info_json = next_page_info_contents[-1][
                    "continuationItemRenderer"
                ]
            except:
                next_page_info_json = next_page_info_contents[2][
                    "continuationItemRenderer"
                ]
        except Exception as e:
            print(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", e)
            traceback.print_exc()
            self.logger.error(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", traceback.print_exc())
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
        return youtube_list_json
        # 유튜브 리스트 json 저장
        # with open("youtube_list.json", 'w') as json_file:
        #     json.dump(youtube_list_json, json_file, ensure_ascii=False, indent=4)

    def scrape_page_list(self, page_list, limit:int):
        for item in page_list:
            try:
                if len(self.result) >= limit:
                    break
                if "videoRenderer" in item:
                    self.result.append(self.get_video_detail(item))
                elif "reelShelfRenderer" in item:
                    for short in item["reelShelfRenderer"]["items"]:
                        if len(self.result) >= limit:
                            break
                        self.result.append(self.get_reel_detail(short))
                elif "reelItemRenderer" in item:
                    self.result.append(self.get_reel_detail(item))
            except Exception as e:
                print(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", e)
                traceback.print_exc()
                self.logger.error(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", traceback.print_exc())
                continue
        return self.result

        
    def get_video_detail(self, json_data):
        video_id = ""
        title = ""
        description = ""
        view_count = 0
        author = ""
        publish_date = ""
        try:
            response = self.request_video_detail(json_data)
            # with open("video_detail.json", 'w', encoding='utf-8') as json_file:
            #     json.dump(response, json_file, ensure_ascii=False, indent=4)
            video_id = self.detail_json["videoId"]
            try:
                title = response["videoDetails"]["title"]
                description = response["videoDetails"]["shortDescription"]
                author = response["videoDetails"]["author"]
            except:
                pass
            try:
                view_count = response["videoDetails"]["viewCount"]
                publish_date = response["microformat"]["playerMicroformatRenderer"]["publishDate"]
            except:
                pass
        except Exception as e:
            print(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", e)
            traceback.print_exc()
            self.logger.error(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", traceback.print_exc())
        finally:
            print(f"type : video \n title : {title}")
            return {
                "VideoID"       : video_id,
                "type"          : "video",
                "title"         : title,
                "description"   : description,
                "viewCount"     : view_count,
                "author"        : author,
                "publishDate"   : publish_date,
            }

    def get_reel_detail(self, json_data):
        video_id = ""
        title = ""
        description = ""
        view_count = 0
        author = ""
        publish_date = ""
        try:
            response = self.request_shorts_detail(json_data)
            video_id = self.detail_json["videoId"]
            try:
                title = response["videoDetails"]["title"]
                description = response["videoDetails"]["shortDescription"]
                author = response["videoDetails"]["author"]
            except:
                pass
            try:
                view_count = response["microformat"]["playerMicroformatRenderer"]["viewCount"]
                publish_date = response["microformat"]["playerMicroformatRenderer"]["publishDate"]
            except:
                pass
            # with open("reel_detail.json", 'w', encoding='utf-8') as json_file:
            #     json.dump(response, json_file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", e)
            traceback.print_exc()
            self.logger.error(f"예기치 못한 에러 \n 에러코드 : {sys.exc_info.__name__}", traceback.print_exc())
        finally:
            print(f"type : shorts \n title : {title}")
            return {
                "videoId"     : video_id,
                "title"       : title,
                "type"        : "shorts",
                "description" : description,
                "view_count"  : view_count,
                "author"      : author,
                "publish_date": publish_date,
            }
        
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
    def request_video_detail(self, json_data):
        self.detail_json["context"][
            "clickTracking"][
            "clickTrackingParams"
            ] = json_data["videoRenderer"][
            "navigationEndpoint"][
            "clickTrackingParams"
            ]
        self.detail_json["videoId"] = json_data["videoRenderer"]["videoId"]
        try:
            self.detail_json["params"] = json_data["videoRenderer"][
                "navigationEndpoint"][
                "watchEndpoint"][
                "playerParams"]
        except:
            self.detail_json["params"] = json_data["videoRenderer"][
            "navigationEndpoint"][
            "reelWatchEndpoint"][
            "playerParams"]
        
        self.detail_json["playbackContext"][
            "contentPlaybackContext"][
            "currentUrl"
        ] = json_data["videoRenderer"][
            "navigationEndpoint"][
            "commandMetadata"][
            "webCommandMetadata"][
            "url"
        ]
        response = self._api_detail_page(self.api_key)
        return response
    
    def request_shorts_detail(self, json_data):
        self.detail_json["context"]["clickTracking"][
            "clickTrackingParams"
        ] = json_data["reelItemRenderer"]["navigationEndpoint"][
            "clickTrackingParams"
        ]
        self.detail_json["videoId"] = json_data["reelItemRenderer"]["videoId"]

        try:
            self.detail_json["params"] = json_data["reelItemRenderer"][
                "navigationEndpoint"][
                "reelWatchEndpoint"][
                "playerParams"]
        except:
            self.detail_json["params"] = json_data["reelItemRenderer"][
                "navigationEndpoint"][
                "watchEndpoint"][
                "playerParams"]

        self.detail_json["playbackContext"]["contentPlaybackContext"][
            "currentUrl"
        ] = json_data["reelItemRenderer"]["navigationEndpoint"][
            "commandMetadata"
        ][
            "webCommandMetadata"
        ][
            "url"
        ]

        self.detail_json["playbackContext"]["contentPlaybackContext"][
            "referer"
        ] = f"https://www.youtube.com/results?search_query={self.keyword}"

        response = self._api_detail_page(self.api_key)
        return response
    def _get_next_page(self):
        # 다음 페이지 가져오기
        initial_data_json = self._api_search_page_next(self.api_key)
        try:
            self.click_tracking_params = initial_data_json[
                "onResponseReceivedCommands"][0][
                "clickTrackingParams"]

            self.continuation_command = initial_data_json[
                "onResponseReceivedCommands"][0][
                "appendContinuationItemsAction"][
                "continuationItems"][1][
                "continuationItemRenderer"][
                "continuationEndpoint"][
                "continuationCommand"][
                "token"]

            self.post_json["continuation"] = self.continuation_command

            # 데이터 가져오기
            youtube_list_json = initial_data_json["onResponseReceivedCommands"][0][
                "appendContinuationItemsAction"][
                "continuationItems"][0][
                "itemSectionRenderer"][
                "contents"]
            return youtube_list_json
        except:
            pass
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
            self._api_search_page_next(key=key)
    def search_list(self, keyword: str, limit: int = 200):
        youtube_list = self.first_page_setting(keyword=keyword)
        self.scrape_page_list(youtube_list, limit=limit)
        while len(self.result) < limit:
            youtube_list = self._get_next_page()
            self.scrape_page_list(youtube_list, limit=limit)
        self.logger.info(f"keyword: {keyword} limit: {limit} result: {len(self.result)}")
        return self.result


if __name__ == "__main__":
    api = Scraper()
    # youtube_list = api.first_page_setting(keyword="떡볶이")
    # result = api.scrape_page_list(youtube_list)
    # # 다음 페이지 가져오기
    # youtube_list2 = api._get_next_page()
    # result2 = api.scrape_page_list(youtube_list2)

    result = api.search_list(keyword="검은콩", limit=400)

    # 다음 페이지를 위한 파라메터 저장

    
    with open("result.json", 'w', encoding='utf-8') as json_file:
        json.dump(result, json_file, ensure_ascii=False, indent=4)