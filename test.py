import youtube_crawler

y = youtube_crawler.Youtube()

res = y.get_info_by_keyword("갈비탕", 10, 1.5)
print(res)
