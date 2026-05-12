import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

# GitHub Secrets 환경 변수
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수 미설정")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 타임존을 서울로 고정하여 시차 문제 방지
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, timezone_id="Asia/Seoul", locale="ko-KR")
        page = context.new_page()

        try:
            print("🔗 eClass 로그인 및 목록 접속...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            # 과제 목록 페이지로 이동
            page.goto("https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom", wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=15000)
            
            cal = Calendar()
            seen_tasks = set()
            task_elements = page.query_selector_all("li.work div.content")
            task_count = len(task_elements)
            print(f"📊 발견된 과제: {task_count}개")

            for i in range(task_count):
                # 목록 페이지 유지를 위해 반복문마다 요소 새로 찾기
                current_tasks = page.query_selector_all("li.work div.content")
                task = current_tasks[i]
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 [{i+1}/{task_count}] '{event_name}' 상세 내용 추출 중...")
                    
                    # 과제 클릭하여 상세 페이지 진입
                    task.click()
                    page.wait_for_load_state("networkidle")
                    
                    # [핵심] 보내주신 스크린샷의 .cont.pb0 태그를 정확히 찾아 텍스트 추출
                    task_description = "상세 내용 없음"
                    try:
                        # 해당 태그가 나타날 때까지 최대 5초 대기
                        page.wait_for_selector(".cont.pb0", timeout=5000)
                        desc_element = page.query_selector(".cont.pb0")
                        if desc_element:
                            task_description = desc_element.inner_text().strip()
                    except:
                        print(f"⚠️ '{event_name}'의 상세 설명 태그를 찾지 못했습니다.")

                    # 다시 목록으로 돌아가기
                    page.go_back()
                    page.wait_for_selector("li.work", timeout=10000)

                    # 날짜 데이터 처리
                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        # 캘린더 메모란(Description) 구성
                        event.description = (
                            f"📌 과목명: {subject}\n"
                            f"⏰ 마감기한: {dates[1]}\n"
                            f"----------------------------\n"
                            f"📝 [과제 상세 설명]\n\n{task_description}\n\n"
                            f"----------------------------\n"
                            f"출처: 군산대 eClass 자동 동기화"
                        )
                        
                        # 알람 설정: 마감 3일 전, 1일 전 오전 9시
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            # 이벤트 시작 시간(begin) 대비 상대적 오프셋 계산
                            trigger_offset = target_time - event.begin
                            event.alarms.append(DisplayAlarm(trigger=trigger_offset))

                        cal.events.add(event)
                        seen_tasks.add(event_name)
                        print(f"✅ 추출 성공: {event_name}")

            # 최종 .ics 파일 저장
            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 업데이트 완료! 모든 과제 내용이 정상 반영되었습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
