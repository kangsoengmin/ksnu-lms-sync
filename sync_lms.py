import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text: return ""
    text = text.strip()
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수가 설정되지 않았습니다.")
        return

    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')
    study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"🔗 eClass 접속 중... ({update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록으로 이동...")
            page.goto(study_url, wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=15000)
            
            assignment_boxes = page.query_selector_all("li.work div.content")
            count = len(assignment_boxes)
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 목록 페이지 다시 로드하여 안정성 확보
                page.goto(study_url, wait_until="domcontentloaded")
                page.wait_for_selector("li.work")
                
                current_items = page.query_selector_all("li.work div.content")
                if i >= len(current_items): break
                
                item = current_items[i]
                title = item.get_attribute("title") or "제목 없음"
                spans = item.query_selector_all("span")
                
                if len(spans) >= 2:
                    subject = spans[0].inner_text().strip()
                    date_text = spans[-1].inner_text().strip()
                    event_name = f"[{subject}] {title}"
                    
                    if event_name in seen_tasks: continue

                    print(f"📖 '{event_name}' 본문 추출 시도...")
                    
                    task_description = "상세 내용을 가져오지 못했습니다."
                    try:
                        # 클릭 이벤트 발생
                        item.dispatch_event("click")
                        # 상세 페이지 로딩 대기 (네트워크 안정화까지)
                        page.wait_for_load_state("networkidle")
                        
                        # [핵심] 군산대 eClass의 과제 상세 본문은 보통 table 내부에 있거나 특정 ID를 가집니다.
                        # 더 포괄적인 셀렉터들을 시도합니다.
                        potential_selectors = [
                            "div.board_view_area", 
                            "div.view_text", 
                            "td.content", 
                            "#content_text",
                            "div.text_area"
                        ]
                        
                        for selector in potential_selectors:
                            content_node = page.query_selector(selector)
                            if content_node:
                                text = clean_text(content_node.inner_text())
                                if text: # 내용이 있는 경우에만 채택
                                    task_description = text
                                    break
                                    
                    except Exception as inner_e:
                        print(f"⚠️ 상세 정보 접근 중 오류: {inner_e}")

                    dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                    if len(dates) == 2:
                        event = Event()
                        event.name = event_name
                        event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                        
                        event.description = (
                            f"과목: {subject}\n\n"
                            f"[과제 내용]\n{task_description}\n\n"
                            f"출처: 군산대 eClass\n"
                            f"최신화 시간: {update_time}"
                        )
                        
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            # [FutureWarning 해결] .serialize() 사용
            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.write(cal.serialize())
            print(f"\n✨ 최종 완료! 총 {len(cal.events)}개의 과제가 동기화되었습니다.")

        except Exception as e:
            print(f"❌ 전체 로직 오류: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
