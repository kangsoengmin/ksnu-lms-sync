import os
import re
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

# GitHub Secrets 환경 변수
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 환경 변수 미설정")
        return

    with sync_playwright() as p:
        # 서버 환경용 Headless 모드
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        try:
            print("🔗 eClass 접속 중...")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")

            print("🔑 로그인 시도 중...")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 내 강의실 홈으로 이동...")
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
                        event.begin = dates[0].replace(".", "-") + ":00"
                        event.end = dates[1].replace(".", "-") + ":00"
                        event.description = f"과목: {subject}\n출처: 군산대 eClass 자동 동기화"
                        
                        # --- [3단계 오전 9시 알람 로직] ---
                        # 알람 설정 리스트: (기준일, 며칠 전)
                        alarm_targets = [
                            (event.begin, -1), # 시작 1일 전
                            (event.end, -1),   # 마감 1일 전
                            (event.end, -3)    # 마감 3일 전
                        ]
                        
                        for base_day, offset in alarm_targets:
                            # 기준일에서 offset만큼 이동 후 오전 9시 정각 설정
                            target_time = base_day.shift(days=offset).replace(hour=9, minute=0, second=0)
                            
                            # 이벤트 시작 시간(begin) 기준의 상대적 오프셋 계산
                            trigger_offset = target_time - event.begin
                            
                            alarm = DisplayAlarm(trigger=trigger_offset)
                            event.alarms.append(alarm)
                        # ------------------------------

                        cal.events.add(event)
                        seen_tasks.add(event_name)
                        print(f"✅ 알람 3종 설정 완료: {event.name}")

            if len(cal.events) > 0:
                with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                    f.writelines(cal.serialize_iter())
                print(f"✨ 성공! {len(cal.events)}개의 일정이 저장되었습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
