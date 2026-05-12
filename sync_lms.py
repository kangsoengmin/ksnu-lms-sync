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
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, timezone_id="Asia/Seoul", locale="ko-KR")
        page = context.new_page()
        cal = Calendar()

        try:
            print("🔗 로그인 및 목록 접속 중...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            list_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(list_url, wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=15000)
            
            seen_tasks = set()
            task_count = len(page.query_selector_all("li.work div.content"))
            print(f"📊 총 {task_count}개의 과제를 발견했습니다.")

            for i in range(task_count):
                event_name = "알 수 없는 과제" # 기본값
                try:
                    current_tasks = page.query_selector_all("li.work div.content")
                    task = current_tasks[i]
                    title = task.get_attribute("title")
                    spans = task.query_selector_all("span")
                    
                    if len(spans) < 2: continue
                        
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 [{i+1}/{task_count}] '{event_name}' 상세 내용 추출 중...")
                    
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    # [스크린샷 반영] .cont.pb0 태그에서 텍스트 추출
                    task_description = "상세 내용 없음"
                    try:
                        page.wait_for_selector(".cont.pb0", timeout=3000)
                        desc_el = page.query_selector(".cont.pb0")
                        if desc_el:
                            task_description = desc_el.inner_text().strip()
                    except:
                        print("⚠️ '.cont.pb0' 태그를 찾을 수 없어 기본 구조로 재시도합니다.")
                        # 혹시나 다른 구조일 경우를 대비한 플랜 B
                        fallback_el = page.query_selector(".board_view_area")
                        if fallback_el: task_description = fallback_el.inner_text().strip()

                    # 목록으로 정상 복귀
                    page.go_back()
                    page.wait_for_selector("li.work", timeout=10000)

                    # 일정 객체 생성 및 알람 세팅
                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"📌 과목명: {subject}\n"
                            f"⏰ 마감기한: {dates[1]}\n"
                            f"----------------------------\n"
                            f"📝 [과제 상세 설명]\n\n{task_description}\n\n"
                            f"----------------------------\n"
                            f"출처: 군산대 eClass 자동 동기화"
                        )
                        
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

                except Exception as inner_e:
                    # 중간에 에러가 나도 프로그램이 죽지 않도록 예외 처리
                    print(f"⚠️ '{event_name}' 처리 중 오류 발생 (건너뜀): {inner_e}")
                    # 에러로 인해 화면이 꼬였을 수 있으니, 과제 목록 주소로 다시 강제 이동 (복구 로직)
                    page.goto(list_url)
                    page.wait_for_selector("li.work")

        except Exception as e:
            print(f"❌ 전체 실행 중 치명적 오류 발생: {e}")
        
        finally:
            # 💡 [핵심] for문이 끝났거나 중간에 에러가 났어도, 여기까지 모은 데이터는 무조건 파일로 굽는다!
            if len(cal.events) > 0:
                with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                    f.writelines(cal.serialize_iter())
                print(f"\n✨ 총 {len(cal.events)}개의 과제가 파일에 정상 업데이트 되었습니다.")
            else:
                print("\n⚠️ 저장할 일정이 없습니다.")
            
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
