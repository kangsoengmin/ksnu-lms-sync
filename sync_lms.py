import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

# GitHub Secrets 환경 변수
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
            
            cal = Calendar()
            seen_tasks = set()
            
            # 목록 개수를 파악합니다.
            task_count = len(page.query_selector_all("li.work div.content"))
            
            for i in range(task_count):
                # 매번 목록을 새로 갱신해야 StaleElement 오류가 나지 않습니다.
                tasks = page.query_selector_all("li.work div.content")
                task = tasks[i]
                
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    # --- [상세 내용 추출 로직] ---
                    print(f"📖 '{event_name}' 상세 내용 추출 시도 중...")
                    task.click() # 상세 페이지 진입
                    page.wait_for_load_state("networkidle")
                    
                    # 본문 내용이 담긴 여러 가능한 셀렉터를 시도합니다.
                    content_selectors = [".board_view_area", ".board_view", ".course_view", "table.view_table"]
                    task_description = "상세 내용 없음"
                    
                    for selector in content_selectors:
                        desc_element = page.query_selector(selector)
                        if desc_element:
                            task_description = desc_element.inner_text().strip()
                            break
                    
                    # 다시 목록으로 돌아가기
                    page.go_back()
                    page.wait_for_selector("li.work")
                    # -----------------------------

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        # [메모란 구성]
                        event.description = (
                            f"📌 과목명: {subject}\n"
                            f"⏰ 마감일: {dates[1]}\n"
                            f"----------------------------\n"
                            f"📝 [과제 내용]\n\n{task_description}\n\n"
                            f"----------------------------\n"
                            f"출처: 군산대 eClass 자동 동기화"
                        )
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            trigger_offset = target_time - event.begin
                            event.alarms.append(DisplayAlarm(trigger=trigger_offset))

                        cal.events.add(event)
                        seen_tasks.add(event_name)
                        print(f"✅ 추출 완료 (내용 포함): {event_name}")

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 성공! 내용이 포함된 {len(cal.events)}개의 일정을 저장했습니다.")

        except Exception as e:
            print(f"❌ 오류 원인 분석 코드를 실행합니다...: {e}")
            # 디버깅을 위해 현재 화면을 캡처하거나 에러 위치를 로깅할 수 있습니다.
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
