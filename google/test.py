import requests
from urllib.parse import unquote, quote
import json
import time

def Send_request(keyword):
    base_url = 'http://localhost:8000/search/google?'
    keywords = f'keywords={quote(keyword)}'
    try:
        res = requests.get(base_url+keywords)

        if res.status_code == 200:
            # results = extract_result(res.text)
            return res.text
        else:
            print(res.status_code)
            return None

    except Exception as e:
        print(e)

def flatten_nested_lists(nested_list):
    try:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
        assert nested_list is list, "입력은 리스트여야 합니다."
    except AssertionError as e:
        return []

    flattened_list = []
    for sublist in nested_list:
        if isinstance(sublist, list):
            flattened_list.extend(flatten_nested_lists(sublist))
        else:
            flattened_list.append(sublist)
    if flattened_list is None:
        return []
    return flattened_list

def extract_result(string):
    assert isinstance(string, str), "입력은 문자열이어야 합니다."

    try:
        data = json.loads(string)
        # print(data)
        # results = flatten_nested_lists(item['result'] for item in data)
        results = data[0]['result']
        # print(results)

        return results
    except json.JSONDecodeError as e:
        pass
    except Exception as e:
        print(f"디코딩 에러 : {e}")
        return None


if __name__ == '__main__':
    max_loop = 10
    cur_loop = 0
    response = ""
    formatted_result = []
    keywords = ['초콜릿']

    formatted_result = []
    while cur_loop < max_loop or response == None or len(formatted_result) <= 0:
        for keyword in keywords:
            response = Send_request(keyword=keyword)
            if response is not None:
                if formatted_result is None:  # Check if formatted_result is None
                    formatted_result = []  # Initialize formatted_result as an empty list
                formatted_result.extend(extract_result(response))
                formatted_result = list(set(formatted_result))

        cur_loop += 1
        time.sleep(1)
        keywords = formatted_result
        print(keywords, len(keywords))
