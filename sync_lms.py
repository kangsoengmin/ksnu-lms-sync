import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

# GitHub Secrets 환경 변수
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text: return ""
    text = text.strip()
    # 3개 이상의 줄바꿈을 2개로 압축
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수가 설정되지 않았습니다.")
        return

    # 최신화 시간 기록 (KST)
    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 뷰포트를 크게 설정하여 요소가 잘 보이게 합니다.
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"🔗 eClass 접속 중... (최신화 시점: {update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록 페이지 이동 중...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            page.wait_for_selector("li.work", timeout=15000)
            
            # 전체 과제 개수 파악
            task_elements = page.query_selector_all("li.work div.content")
            count = len(task_elements)
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 매번 목록 요소를 새로 가져와야 에러가 안 납니다.
                current_tasks = page.query_selector_all("li.work div.content")
                if i >= len(current_tasks): break
                
                target_task = current_tasks[i]
                title = target_task.get_attribute("title")
                spans = target_task.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 '{event_name}' 정보 추출 중...")
                    
                    try:
                        # [핵심 수정] 클릭 에러 방지 로직
                        target_task.scroll_into_view_if_needed() # 클릭 전 스크롤
                        target_task.click(force=True, timeout=10000) # 강제 클릭 옵션
                        page.wait_for_load_state("networkidle")
                        
                        desc_element = page.query_selector(".board_view_area")
                        task_description = clean_text(desc_element.inner_text()) if desc_element else "내용 없음"
                        
                        page.go_back()
                        page.wait_for_selector("li.work")
                    except Exception as click_err:
                        print(f"⚠️ 클릭 실패로 기본 정보만 저장합니다: {click_err}")
                        task_description = "상세 내용을 가져오지 못했습니다."

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        # 시차 보정 (KST 명시)
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"과목: {subject}\n\n"
                            f"[과제 내용]\n{task_description}\n\n"
                            f"출처: 군산대 eClass\n"
                            f"최신화 시간: {update_time}"
                        )
                        
                        # 알람: 마감 3일 전, 1일 전 오전 9시
                        for d in [-3, -1]:
                            t_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=t_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 완료! 모든 정보가 시차 보정 및 최신화 시간과 함께 저장되었습니다.")

        except Exception as e:
            print(f"❌ 전체 로직 오류: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
