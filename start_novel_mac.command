#!/bin/bash
# 맥에서 더블클릭하면 웹소설 자동 집필기(화면 방식)가 켜집니다.
# (처음엔 "확인되지 않은 개발자" 경고가 뜰 수 있어요 → 마우스 우클릭 > 열기)
cd "$(dirname "$0")"
echo "필요한 라이브러리를 확인/설치합니다..."
pip3 install -r requirements.txt
echo ""
python3 novel_web.py
