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
    text = text.strip()
    # 3개 이상의 연속된 줄바꿈을 2개로 압축하여 불필요한 공백 제거
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수가 설정되지 않았습니다.")
        return

    # 현재 실행 시간을 'YYYY-MM-DD HH:mm' 형식으로 저장
    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            print(f"🔗 eClass 접속 중... (업데이트 시간: {update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            page.wait_for_selector("li.work", timeout=15000)
            count = len(page.query_selector_all("li.work div.content"))
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
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

                    print(f"📖 '{event_name}' 정보 가져오는 중...")
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    description_element = page.query_selector(".board_view_area") 
                    task_description = clean_text(description_element.inner_text()) if description_element else ""
                    
                    page.go_back()
                    page.wait_for_selector("li.work")

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        # [핵심 수정] 메모란 하단에 최신화 일시 추가
                        event.description = (
                            f"과목: {subject}\n\n"
                            f"[과제 내용]\n{task_description}\n\n"
                            f"출처: 군산대 eClass\n"
                            f"최신화 시간: {update_time}"
                        )
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 완료! 모든 일정에 최신화 시간({update_time})이 기록되었습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
