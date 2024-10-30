from fastapi import FastAPI
from crawl_manager import Crawler
from youtube_crawler import Youtube

import re
import time

app = FastAPI()
crawler = Crawler()

youtube = Youtube()


@app.get("/search/google")
async def search_google(keywords: str):
    results = default_search(keywords=keywords, limit=50, type='Google')
    return results

@app.get("/search/naver")
async def search_naver(keywords: str):
    # result = crawler.GetData(keyword)
    result = default_search(keywords=keywords, limit=50, type='Naver')
    return result

@app.get("/search/naver/popular")
async def search_naver_popular(keywords: str):
    result = default_search(keywords=keywords, limit=50, type='NaverPopular')
    return result

@app.get("/search/navershopping")
async def search_navershopping(keywords: str):
    result = default_search(keywords=keywords, limit=25, delay=0.8, type='NaverShopping')
    return result

# limit = 읽어올 영상 개수 sleep_sec = 다음 영상 읽기전 기다릴 시간 (필수 0은 위험함)
@app.get("/search/youtube")
async def search_youtube(keywords: str):
    keywords = keywords.split(',')
    result = []
    for index, keyword in enumerate(keywords):
        data = {
            'keyword':keyword,
            'result':youtube.get_info_by_keyword(keyword=keyword, limit=250, sleep_sec=0.2)
        }
        print(f'{index}   {data}')
        result.append(data)
    if len(result) == 0 :
        for index, keyword in enumerate(keywords):
            data = {
                'keyword':keyword,
                'result':youtube.get_info_by_keyword(keyword=keyword, limit=250, sleep_sec=0.2)
            }
            print(f'{index}   {data}')
            result.append(data)
    return result

def default_search(keywords:str, limit:int, type:str, delay:float=0.0):
    crawler = Crawler()
    crawler.Set_Browser()
    type_map = {
        'Naver':crawler.Search_Naver,
        'NaverPopular':crawler.Search_Naver_Popular,
        'NaverShopping':crawler.Search_NaverShopping,
        'Google':crawler.Search_Google,
    }
    
    # keywords = ["단어",'카페인','함장','합참','군대','양구','포스코','취업','청창사','사과', '바나나', '복숭아', '포도', '오렌지', '딸기', '체리', '자두', '키위', '배','수박', '메론', '파인애플', '레몬', '라임', '살구', '블루베리', '아보카도', '감', '참외','망고', '밤', '토마토', '파파야', '자몽', '귤', '감귤', '포도', '패션후르츠', '살구', '두리안','석류', '아로니아', '키위', '시원과', '모과', '레드향', '무화과', '산딸기', '곶감', '톤끼', '딸기','애플망고', '홍시', '복분자', '미나리', '배', '아미야', '화이트포도', '멜론', '라즈베리', '파파야','양파', '대추', '석류', '무화과', '국화','장미', '튤립', '백합', '국화', '안개꽃', '무궁화', '개나리', '코스모스', '매화', '해바라기','튤립', '달리아', '카네이션', '해바라기', '제비꽃', '데이지', '프리지아', '라벤더', '스위트피', '국화','수국', '수련', '동백', '자스민', '계단꽃', '왕벚나무', '베고니아', '하이비스커스', '라넌큘러스', '모란','진달래', '한련화', '계수나무', '산수유', '솔잎나무', '메타세쿼이아', '목련', '실버버튼', '수달', '홍길','달무리', '안개꽃', '수련', '밤', '산수유', '패란', '제비꽃', '마가렛', '스위트피', '라넌큘러스', '한련화','동백', '패란', '라벤더', '왕벚나무', '코스모스', '상아수야', '무궁화', '국화', '양귀비', '프리지아','카네이션', '다알리아', '메타세쿼이아', '베고니아', '샤스타', '솔잎나무', '벚나무', '진달래', '카모마일', '레이디핑크','홍길', '장미','책', '펜', '노트북', '휴대폰', '의자', '테이블', '컴퓨터', '신발', '가방', '자동차','커피머신', '텔레비전', '냉장고', '전자레인지', '선풍기', '에어컨', '세탁기', '건조기', '모니터', '키보드','마우스', '스마트워치', '블루투스 스피커', '냄비', '프라이팬', '식기세척기', '청소기', '계란', '우유', '과자','초콜릿', '과일', '야채', '수건', '칫솔', '치약', '샴푸', '린스', '비누', '세제', '휴지', '칼', '가위','발찌', '귀걸이', '시계', '목걸이', '안경', '모자', '양말', '장갑', '티셔츠', '청바지', '원피스', '스커트','수영복', '비키니', '양산', '우산', '컵', '접시', '수저', '포크', '나이프', '젓가락', '텀블러', '밥솥','전기포트', '밥숟가락', '젓갈', '케이크', '케첩', '머스타드', '소금', '후추', '설탕', '생수', '음료수','콜라', '사이다', '차', '우유', '주스', '맥주', '소주', '와인', '꽃병', '화분', '초', '향수', '샤워젤','바디로션', '선글라스', '카드지갑', '종이지갑', '지갑', '머그컵', '커피잔', '찻잔', '스푼', '호스', '양말','건전지', '휴대폰 충전기', '노트북 충전기', '헤어드라이어', '카메라', '빔프로젝터', '면도기', '우산', '스키','스노보드', '텐트', '방수 팬츠', '담요', '손목 시계', '벨트', '운동화', '가발', '청소용품', '전자 담배','안마기', '먹물', '인형', '비디오 게임', '보드게임', '운동기구', '헬스기구', '건강 보조제', '화장품', '의약품','의료기기', '휴대폰 케이스', '노트북 케이스', '신문', '잡지', '서적', '과자', '젤리', '사탕', '초콜릿', '김밥','라면', '샌드위치', '피자', '스테이크', '초밥', '햄버거', '타코', '샐러드','김밥', '라면', '떡볶이', '순대', '어묵', '만두', '냉면', '비빔밥', '불고기', '갈비',                 '삼겹살', '햄버거', '치킨', '피자', '파스타', '스테이크', '초밥', '샤시미', '우동', '소바','우동', '소바', '라멘', '오코노미야끼', '타코야끼', '유부초밥', '야끼소바', '해물파전', '팟타이', '푸딩','마카롱', '크로와상', '도넛', '와플', '아이스크림', '딸기케이크', '초콜릿케이크', '치즈케이크', '타르트','빵', '케이크', '크림빵', '피자빵', '단팥빵', '호빵', '바게트', '크로와상', '브리오슈', '머핀','샌드위치', '핫도그', '샐러드', '스프', '짜장면', '짬뽕', '탕수육', '볶음밥', '고추잡채', '마파두부','꿔바로우', '연탄꼬치', '탄탄면', '마라탕', '마라샹궈', '뚝배기불고기', '훠궈', '짜조', '꼬치', '닭발','닭꼬치', '보쌈', '족발', '치즈퐁듀', '편육', '물회', '해물찜', '곱창', '대창', '막창', '삼겹살','생선구이', '양념치킨', '감자튀김', '샐러드', '스프', '김치찌개', '된장찌개', '부대찌개', '전', '갈비탕','설렁탕', '감자탕', '뼈해장국', '육개장', '순두부찌개', '물냉면', '비빔냉면', '잔치국수', '칼국수','막국수', '쫄면', '물만두', '물동동', '물밀면', '치즈라면', '짜파게티', '열무냉면', '열무국수', '비빔국수','삼각김밥', '자장면', '짜장면', '짬뽕', '마파두부', '짜조', '볶음밥', '깐풍기', '탕수육', '불고기','불닭볶음면', '짜파게티', '엽떡', '떡국', '떡볶이', '튀김', '김밥', '순대', '어묵', '냉면', '갈비','삼겹살', '치킨', '피자', '햄버거', '샐러드', '스프', '만두', '토스트', '핫도그', '오므라이스', '김치볶음밥','된장찌개', '부대찌개', '순두부찌개', '청국장', '김치찌개', '감자탕', '설렁탕', '갈비탕', '된장국', '고추장찌개','후라이드치킨', '양념치킨', '마라탕', '마라샹궈', '팟타이', '짜조', '닭발', '닭꼬치', '감자튀김', '치즈퐁듀','라멘', '우동', '소바', '나베', '샤브샤브', '오꼬노미야끼','망치', '드라이버']
    keywords = re.sub(r"[\'\"]", "", keywords)
    keywords = keywords.split(',')

    total = len(keywords)
    print(f'총 {total}건 {type} 검색 시작')
    current = 0
    current_limit = limit
    sucess_count=0
    failed_count=0

    results = []
    for keyword in keywords:
        if current > current_limit:
            crawler.Set_Browser()
            current_limit += limit
        result, succesed = type_map[type](keyword, delay)
        # result, succes = crawler.Search(keyword)
        if succesed:
            sucess_count+=1
        else:
            failed_count+=1
        results.append(result)

        print(f'{current} {result}\n')
        current+=1
        time.sleep(delay)
    return results


