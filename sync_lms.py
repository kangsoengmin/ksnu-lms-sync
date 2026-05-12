import os
import re
import arrow  # 타임존 처리를 위해 필요
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

            print("🚀 과제 데이터 추출 중...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            page.wait_for_selector("li.work", timeout=15000)
            assignments = page.query_selector_all("li.work div.content")
            
            cal = Calendar()
            seen_tasks = set()
            
            for task in assignments:
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    
                    event_name = f"[{subject}] {title}"
                    if event_name in seen_tasks:
                        continue
                    
                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        
                        # [핵심 수정] 한국 시간(Asia/Seoul)으로 명시하여 파싱
                        # ics 라이브러리는 arrow 객체를 지원합니다.
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = f"과목: {subject}\n군산대 eClass 자동 동기화"
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        alarm_days = [-3, -1]
                        for d in alarm_days:
                            # 한국 시간 기준으로 전날 오전 9시 계산
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            
                            # 시작 시간(begin) 대비 상대적 오프셋 계산
                            trigger_offset = target_time - event.begin
                            event.alarms.append(DisplayAlarm(trigger=trigger_offset))

                        cal.events.add(event)
                        seen_tasks.add(event_name)
                        print(f"✅ 추출 완료 (KST 적용): {event_name}")

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 시차 보정 완료! 총 {len(cal.events)}개의 일정이 저장되었습니다.")

        except Exception as e:
            print(f"❌ 실행 중 오류 발생: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
