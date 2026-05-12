import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text: return ""
    text = text.strip()
    # 연속된 줄바꿈 정리
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수가 설정되지 않았습니다.")
        return

    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 안정적인 렌더링을 위해 브라우저 크기를 크게 설정
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"🔗 eClass 접속 중... (업데이트 시간: {update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록으로 이동...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            page.wait_for_selector("li.work", timeout=15000)
            
            # 목록 전체를 먼저 확보
            assignments_list = page.query_selector_all("li.work div.content")
            count = len(assignments_list)
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 목록 갱신 (상세 페이지 갔다 오면 엘리먼트가 새로고침됨)
                current_items = page.query_selector_all("li.work div.content")
                if i >= len(current_items): break
                
                item = current_items[i]
                title = item.get_attribute("title")
                spans = item.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 '{event_name}' 본문 읽는 중...")
                    
                    task_description = "내용 없음"
                    try:
                        # 클릭 정확도 향상: 제목 텍스트를 직접 클릭하거나 강제 클릭
                        item.scroll_into_view_if_needed()
                        item.click(force=True)
                        
                        # [핵심] 본문이 로드될 때까지 여러 후보 셀렉터 확인
                        # .board_view_area(표준) 또는 .view_text(기타) 등
                        page.wait_for_selector(".board_view_area, .view_text, .view_content", timeout=7000)
                        
                        desc_element = page.query_selector(".board_view_area") or page.query_selector(".view_text")
                        if desc_element:
                            task_description = clean_text(desc_element.inner_text())
                        
                        page.go_back()
                        page.wait_for_selector("li.work", timeout=10000)
                    except Exception as inner_e:
                        print(f"⚠️ 본문 추출 실패(기본값 사용): {inner_e}")
                        # 실패 시 다시 목록으로 복구 시도
                        page.goto(study_url, wait_until="networkidle")

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        # 한국 시간(KST) 시차 보정 적용
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"과목: {subject}\n\n"
                            f"[과제 내용]\n{task_description}\n\n"
                            f"출처: 군산대 eClass\n"
                            f"최신화 시간: {update_time}"
                        )
                        
                        # 알람: 마감 3일 전, 1일 전 오전 9시 (총 2개)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 완료! 모든 정보가 업데이트되었습니다. ({update_time})")

        except Exception as e:
            print(f"❌ 전체 로직 오류: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
