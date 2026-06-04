#!/bin/bash

# 기본 값 설정
TAG="latest"

# 옵션 파싱
while getopts "n:" opt; do
  case $opt in
    n)
      IMAGE_NAME="$OPTARG"
      ;;
    *)
      echo "Usage: $0 -n image_name"
      exit 1
      ;;
  esac
done

# IMAGE_NAME이 설정되지 않은 경우 오류 메시지 출력
if [ -z "$IMAGE_NAME" ]; then
  echo "Error: -n option (image name) is required"
  echo "Usage: $0 -n image_name"
  exit 1
fi

# Docker 이미지 빌드
echo "Docker 이미지를 빌드 중입니다..."
docker build -t ${IMAGE_NAME}:${TAG} .

# Docker 이미지 푸시
echo "Docker 이미지를 레지스트리에 푸시 중입니다..."
docker push ${IMAGE_NAME}:${TAG}


