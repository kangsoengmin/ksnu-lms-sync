import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm
from datetime import timedelta

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 서버 환경에서 가독성을 높이기 위해 창 크기를 충분히 키움
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"🔗 eClass 접속 중... ({update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.press("#pw", "Enter")

            print("🚀 과제 목록으로 이동...")
            study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"
            page.goto(study_url, wait_until="networkidle")

            # 과제 요소가 나타날 때까지 대기
            page.wait_for_selector("li.work", timeout=15000)
            
            # 실제 정보가 들어있는 과제 박스들만 필터링
            assignment_boxes = page.query_selector_all("li.work div.content")
            count = len(assignment_boxes)
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 목록 갱신
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

                    print(f"📖 '{event_name}' 본문 읽는 중...")
                    
                    task_description = "상세 내용을 가져오지 못했습니다."
                    try:
                        # [해결책] 물리적 클릭 대신 JS 이벤트를 직접 발생시켜 '가시성/뷰포트 에러' 우회
                        item.dispatch_event("click")
                        
                        # 페이지 로딩 대기
                        page.wait_for_load_state("domcontentloaded")
                        
                        # 본문 영역을 찾기 위한 다양한 후보군 (Selector 최적화)
                        content_selectors = [".board_view_area", ".view_text", ".view_content", "#content_text", ".content_area"]
                        
                        found_content = False
                        for selector in content_selectors:
                            try:
                                # 각 셀렉터가 나타나는지 짧게 확인
                                element = page.wait_for_selector(selector, timeout=3000)
                                if element:
                                    task_description = clean_text(element.inner_text())
                                    found_content = True
                                    break
                            except:
                                continue
                        
                        if not found_content:
                            print(f"⚠️ '{event_name}'의 본문 셀렉터를 찾지 못했습니다.")
                        
                        # 목록으로 복귀 (뒤로 가기가 안 될 경우를 대비해 URL 직접 이동 병행)
                        page.go_back()
                        page.wait_for_selector("li.work", timeout=5000)
                        
                    except Exception as inner_e:
                        print(f"⚠️ 상세 정보 접근 실패: {inner_e}")
                        page.goto(study_url, wait_until="networkidle")

                    # 날짜 처리
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
                        
                        # 알람 설정 (마감 3일 전, 1일 전 오전 9시)
                        for d in [-3, -1]:
                            target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                            event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                        cal.events.add(event)
                        seen_tasks.add(event_name)

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.writelines(cal.serialize_iter())
            print(f"\n✨ 최종 완료! 총 {len(cal.events)}개의 정보가 동기화되었습니다.")

        except Exception as e:
            print(f"❌ 전체 로직 오류: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
