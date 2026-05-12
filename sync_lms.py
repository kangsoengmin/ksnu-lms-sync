import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text:
        return ""
    # 1. 양끝 공백 제거
    text = text.strip()
    # 2. 3개 이상의 연속된 줄바꿈(\n\n\n...)을 2개(\n\n)로 압축
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    # 3. 각 줄의 끝에 붙은 불필요한 공백들 제거
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수가 설정되지 않았습니다.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            print("🔗 eClass 접속 및 로그인 중...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록으로 이동...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            page.wait_for_selector("li.work", timeout=15000)
            
            # 과제 요소들을 다시 가져옵니다.
            count = len(page.query_selector_all("li.work div.content"))
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 매번 요소를 새로 탐색 (Stale Element 방지)
                task_elements = page.query_selector_all("li.work div.content")
                if i >= len(task_elements): break
                
                task = task_elements[i]
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 '{event_name}' 상세 내용 정리 중...")
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    # 상세 내용 추출 및 정제
                    description_element = page.query_selector(".board_view_area") 
                    task_description = ""
                    if description_element:
                        raw_desc = description_element.inner_text()
                        # [핵심 수정] 텍스트 정제 함수 호출
                        task_description = clean_text(raw_desc)
                    
                    page.go_back()
                    page.wait_for_selector("li.work")

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = f"과목: {subject}\n\n[과제 내용]\n{task_description}\n\n출처: 군산대 eClass"
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 내용 정제 완료! 총 {len(cal.events)}개의 일정이 저장되었습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
