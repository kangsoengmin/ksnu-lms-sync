import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 환경 변수(LMS_ID, LMS_PW)가 설정되지 않았습니다.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 시차 방지를 위해 타임존 설정 포함
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, timezone_id="Asia/Seoul")
        page = context.new_page()

        try:
            print("🔗 로그인 시도 중...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록 로드 중...")
            page.goto("https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom", wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=20000)
            
            cal = Calendar()
            seen_tasks = set()
            
            # 목록 요소들을 가져옵니다.
            task_elements = page.query_selector_all("li.work div.content")
            task_count = len(task_elements)
            print(f"📊 발견된 과제 수: {task_count}개")

            for i in range(task_count):
                try:
                    # 매 루프마다 요소를 새로 갱신 (Stale Element 방지)
                    current_tasks = page.query_selector_all("li.work div.content")
                    task = current_tasks[i]
                    title = task.get_attribute("title")
                    spans = task.query_selector_all("span")
                    
                    if len(spans) < 2: continue
                    
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 [{i+1}/{task_count}] '{event_name}' 내용 추출 중...")
                    
                    # 상세 페이지 진입
                    task.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000) # 로딩 대기 시간 추가

                    # 내용 추출 (여러 셀렉터 시도)
                    task_description = "상세 내용 없음"
                    for sel in [".board_view_area", ".board_view", ".course_view", "table"]:
                        el = page.query_selector(sel)
                        if el and len(el.inner_text().strip()) > 5:
                            task_description = el.inner_text().strip()
                            break
                    
                    page.go_back()
                    page.wait_for_selector("li.work", timeout=15000)

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.description = f"📌 과목: {subject}\n⏰ 마감: {dates[1]}\n\n📝 [내용]\n{task_description}\n\n출처: 군산대 eClass"
                        
                        # 알람 설정
                        for d in [-3, -1]:
                            target = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

                except Exception as inner_e:
                    print(f"⚠️ '{event_name}' 처리 중 건너뜀: {inner_e}")
                    page.goto("https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom")
                    page.wait_for_selector("li.work")

            # 최종 파일 저장
            if len(cal.events) > 0:
                with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                    f.writelines(cal.serialize_iter())
                print(f"✨ 업데이트 성공! ({len(cal.events)}개 일정)")
            else:
                print("⚠️ 저장할 일정이 없습니다.")

        except Exception as e:
            print(f"❌ 치명적 오류 발생: {e}")
            raise e # 에러를 다시 던져서 액션이 실패(Red X)로 뜨게 함
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
