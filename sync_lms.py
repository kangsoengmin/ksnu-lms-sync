import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

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
            
            # 과제 링크들을 미리 확보합니다.
            assignment_elements = page.query_selector_all("li.work div.content")
            
            cal = Calendar()
            seen_tasks = set()
            
            # 상세 페이지를 왔다 갔다 해야 하므로 인덱스로 접근합니다.
            for i in range(len(assignment_elements)):
                # 매번 요소를 새로 찾아야 'Stale Element' 에러를 방지할 수 있습니다.
                task = page.query_selector_all("li.work div.content")[i]
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    # --- [상세 내용 추출 로직 시작] ---
                    print(f"📖 '{event_name}' 내용 읽는 중...")
                    task.click() # 과제 클릭하여 상세 페이지 진입
                    page.wait_for_load_state("networkidle")
                    
                    # 상세 내용이 들어있는 영역의 텍스트를 가져옵니다.
                    # eClass의 전형적인 본문 영역 셀렉터를 사용합니다.
                    description_element = page.query_selector(".board_view_area") 
                    task_description = ""
                    if description_element:
                        task_description = description_element.inner_text().strip()
                    
                    # 다시 목록으로 돌아가기
                    page.go_back()
                    page.wait_for_selector("li.work")
                    # -----------------------------------

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        # 가져온 내용을 캘린더 메모란에 넣습니다.
                        event.description = f"과목: {subject}\n\n[과제 내용]\n{task_description}\n\n출처: 군산대 eClass"
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 내용 포함 완료! 총 {len(cal.events)}개의 일정이 저장되었습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
