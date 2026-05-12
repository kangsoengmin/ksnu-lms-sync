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
        print("❌ 오류: 환경 변수 미설정")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            print("🔗 eClass 로그인 및 목록 로드...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            page.goto("https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom", wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=15000)
            
            cal = Calendar()
            seen_tasks = set()
            task_count = len(page.query_selector_all("li.work div.content"))
            
            for i in range(task_count):
                tasks = page.query_selector_all("li.work div.content")
                task = tasks[i]
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    if event_name in seen_tasks: continue

                    # --- 상세 내용 추출 로직 ---
                    print(f"📖 '{event_name}' 상세 내용 읽는 중...")
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    content_selectors = [".board_view_area", ".board_view", ".course_view", "table.view_table"]
                    task_description = "상세 내용 없음"
                    for selector in content_selectors:
                        desc_element = page.query_selector(selector)
                        if desc_element:
                            task_description = desc_element.inner_text().strip()
                            break
                    
                    page.go_back()
                    page.wait_for_selector("li.work")
                    # -------------------------

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"📌 과목명: {subject}\n"
                            f"⏰ 마감일: {dates[1]}\n"
                            f"----------------------------\n"
                            f"📝 [과제 내용]\n\n{task_description}\n\n"
                            f"----------------------------\n"
                            f"출처: 군산대 eClass 자동 동기화"
                        )
                        
                        for d in [-3, -1]:
                            t_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=t_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 내용 포함 업데이트 완료!")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
