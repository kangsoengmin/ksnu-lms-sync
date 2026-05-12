import os
import re
from playwright.sync_api import sync_playwright
from ics import Calendar, Event

# GitHub Secrets에 저장할 환경 변수명을 읽어옵니다.
# 로컬 테스트 시에는 이 변수들에 직접 값을 넣어도 되지만, GitHub 업로드 전에는 아래처럼 유지하세요.
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수(LMS_ID, LMS_PW)가 설정되지 않았습니다.")
        return

    with sync_playwright() as p:
        # 서버(GitHub) 환경에서는 브라우저 창을 띄우지 않는 headless 모드로 실행합니다.
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

            # 로그인 후 '내 강의실 홈'으로 이동
            print("🚀 내 강의실 홈으로 이동...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            # 일정 위젯 로드 대기
            page.wait_for_selector("li.work", timeout=15000)
            assignments = page.query_selector_all("li.work div.content")
            
            cal = Calendar()
            seen_tasks = set() # 중복 제거용 집합
            
            for task in assignments:
                title = task.get_attribute("title")
                spans = task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    
                    # 중복 체크 (과목-제목-날짜 조합)
                    task_id = f"{subject}-{title}-{date_text}"
                    if task_id in seen_tasks:
                        continue
                    
                    # 날짜 추출 (YYYY.MM.DD HH:MM)
                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    
                    if len(dates) == 2:
                        event = Event()
                        event.name = f"[{subject}] {title}"
                        # ics 표준 형식으로 변환
                        event.begin = dates[0].replace(".", "-") + ":00"
                        event.end = dates[1].replace(".", "-") + ":00"
                        event.description = f"과목: {subject}\n출처: 군산대 eClass 자동 동기화"
                        
                        cal.events.add(event)
                        seen_tasks.add(task_id)
                        print(f"✅ 추가 완료: {event.name}")

            # .ics 파일 저장
            if len(cal.events) > 0:
                with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                    f.writelines(cal.serialize_iter())
                print(f"✨ 총 {len(cal.events)}개의 일정이 저장되었습니다.")
            else:
                print("⚠️ 저장할 일정이 없습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
        
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()