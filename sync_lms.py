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
    # 연속된 줄바꿈을 깔끔하게 정리
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID or not USER_PW:
        print("❌ 오류: 환경 변수 미설정")
        return

    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')
    # 메인 대시보드(모든 과제 리스트) 주소
    study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 충분히 큰 화면으로 실행
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"🔑 로그인 중... (업데이트 시간: {update_time})")
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")

            print("🚀 메인 리스트에서 과제 제목 클릭 및 내용 추출 시작...")
            page.goto(study_url, wait_until="networkidle")
            page.wait_for_selector("li.work", timeout=20000)
            
            # 과제 박스들 확보
            assignment_boxes = page.query_selector_all("li.work div.content")
            count = len(assignment_boxes)
            
            cal = Calendar()
            seen_tasks = set()
            
            for i in range(count):
                # 매번 목록 페이지를 다시 로드하여 요소 만료(Stale) 방지
                page.goto(study_url, wait_until="domcontentloaded")
                page.wait_for_selector("li.work")
                
                # 현재 순서의 과제 제목 요소 탐색
                current_items = page.query_selector_all("li.work div.content")
                if i >= len(current_items): break
                
                target_item = current_items[i]
                title = target_item.get_attribute("title") or "제목 없음"
                
                # 'work_X' 같은 빈 데이터 필터링
                if not title or "work_" in title: continue

                spans = target_item.query_selector_all("span")
                if len(spans) < 2: continue

                subject = spans[0].inner_text().strip()
                date_text = spans[-1].inner_text().strip()
                event_name = f"[{subject}] {title}"
                
                if event_name in seen_tasks: continue

                print(f"📖 [{i+1}/{count}] '{event_name}' 제목 클릭 중...")
                
                task_description = "상세 내용을 가져오지 못했습니다."
                try:
                    # [핵심] 제목(태그)을 자바스크립트로 직접 클릭 (뷰포트 밖 에러 방지)
                    page.evaluate("(el) => el.click()", target_item)
                    
                    # 상세 페이지 로딩 대기
                    page.wait_for_load_state("networkidle")
                    
                    # 본문 내용 추출 (다양한 본문 태그 대응)
                    desc_node = page.query_selector(".board_view_area") or page.query_selector(".view_content") or page.query_selector("td.content")
                    if desc_node:
                        task_description = clean_text(desc_node.inner_text())
                except Exception as click_err:
                    print(f"   ⚠️ 클릭 또는 추출 실패: {click_err}")

                # 날짜 처리 및 일정 생성
                dates = re.findall(r"(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})", date_text)
                if len(dates) == 2:
                    event = Event()
                    event.name = event_name
                    # 한국 시간 시차 보정
                    event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    
                    event.description = (
                        f"과목: {subject}\n\n"
                        f"[과제 내용]\n{task_description}\n\n"
                        f"출처: 군산대 eClass\n"
                        f"최신화 시간: {update_time}"
                    )
                    
                    # 알람 설정: 마감 3일 전, 1일 전 오전 9시
                    for d in [-3, -1]:
                        target_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                        event.alarms.append(DisplayAlarm(trigger=target_time - event.begin))

                    cal.events.add(event)
                    seen_tasks.add(event_name)
                    print(f"   ✅ 일정 추가 완료")

            # .ics 파일 저장
            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.write(cal.serialize())
            print(f"\n✨ 최종 완료! 총 {len(cal.events)}개의 정보가 동기화되었습니다.")

        except Exception as e:
            print(f"❌ 전체 프로세스 오류: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
