import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수 미설정")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 타임존 시차 문제를 방지하기 위해 컨텍스트 설정에 타임존 명시
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, timezone_id="Asia/Seoul")
        page = context.new_page()

        try:
            print("🔗 eClass 로그인 시도...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록으로 이동...")
            page.goto("https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom", wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=15000)
            
            cal = Calendar()
            seen_tasks = set()
            tasks_to_process = page.query_selector_all("li.work div.content")
            task_count = len(tasks_to_process)
            print(f"📊 총 {task_count}개의 과제를 발견했습니다.")

            for i in range(task_count):
                # 목록 페이지를 유지하기 위해 매번 요소를 새로 찾습니다.
                current_tasks = page.query_selector_all("li.work div.content")
                task = current_tasks[i]
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    if event_name in seen_tasks: continue

                    print(f"📖 [{i+1}/{task_count}] '{event_name}' 상세 읽기 시작...")
                    
                    # 상세 내용 추출 (클릭 후 이동)
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    # 본문 텍스트가 있을 법한 모든 구역을 탐색
                    task_description = "상세 내용 없음"
                    selectors = [".board_view_area", ".board_view", ".course_view", ".view_content", "table"]
                    for sel in selectors:
                        desc_el = page.query_selector(sel)
                        if desc_el:
                            content = desc_el.inner_text().strip()
                            if len(content) > 10: # 너무 짧은 텍스트는 제외
                                task_description = content
                                break
                    
                    print(f"✅ 내용 추출 완료 ({len(task_description)}자)")
                    
                    # 다시 목록으로
                    page.go_back()
                    page.wait_for_selector("li.work", timeout=10000)

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        # KST 타임존 적용
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"📌 과목명: {subject}\n"
                            f"⏰ 마감일: {dates[1]}\n"
                            f"----------------------------\n"
                            f"📝 [과제 상세 내용]\n\n{task_description}\n"
                            f"----------------------------\n"
                            f"출처: 군산대 eClass 자동 동기화"
                        )
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            # 파일 저장
            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 모든 작업 성공! 파일이 업데이트되었습니다.")

        except Exception as e:
            print(f"❌ 실행 중 오류 발생: {e}")
            # 에러가 나더라도 지금까지 긁어온 게 있다면 저장 시도
            if len(cal.events) > 0:
                with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                    f.writelines(cal.serialize_iter())
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
