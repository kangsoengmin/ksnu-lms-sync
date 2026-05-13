import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

# GitHub Secrets에서 정보 가져오기
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text: return ""
    text = text.strip()
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID: return
    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')
    study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"

    with sync_playwright() as p:
        # 서버용이므로 headless=True, slow_mo 제거
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome", wait_until="domcontentloaded")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")

            cal = Calendar()
            seen_tasks = set()
            current_idx = 0

            while True:
                page.goto(study_url, wait_until="domcontentloaded")
                page.wait_for_selector("li.work", timeout=20000)
                items = page.query_selector_all("li.work div.content")
                
                if current_idx >= len(items): break
                
                target = items[current_idx]
                title = target.get_attribute("title") or ""
                spans = target.query_selector_all("span")
                
                if len(spans) < 2 or ("work_" in title and len(title) < 10):
                    current_idx += 1
                    continue

                subject = spans[0].inner_text().strip()
                date_text = spans[-1].inner_text().strip()
                event_name = f"[{subject}] {title}"
                
                if event_name in seen_tasks:
                    current_idx += 1
                    continue

                task_description = "상세 내용을 가져오지 못했습니다."
                try:
                    target.scroll_into_view_if_needed()
                    page.evaluate("(el) => el.click()", target)
                    page.wait_for_selector(".cont.pb0, .board_view_area", timeout=8000)
                    
                    content_element = page.query_selector(".cont.pb0") or page.query_selector(".board_view_area")
                    if content_element:
                        task_description = clean_text(content_element.inner_text())

                except: pass

                dates = re.findall(r"(\d{4}\.\d.2}\.\d{2} \d{2}:\d{2})", date_text)
                if len(dates) == 2:
                    event = Event()
                    event.name = event_name
                    event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    event.description = f"과목: {subject}\n\n[과제 내용]\n{task_description}\n\n최신화 시간: {update_time}"
                    
                    for d in [-3, -1]:
                        t_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                        event.alarms.append(DisplayAlarm(trigger=t_time - event.begin))
                    cal.events.add(event)
                    seen_tasks.add(event_name)

                current_idx += 1

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.write(cal.serialize())

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()import os
import re
import arrow
from playwright.sync_api import sync_playwright
from ics import Calendar, Event, DisplayAlarm

# GitHub Secrets에서 정보 가져오기
USER_ID = os.environ.get("LMS_ID")
USER_PW = os.environ.get("LMS_PW")

def clean_text(text):
    if not text: return ""
    text = text.strip()
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    text = '\n'.join([line.rstrip() for line in text.splitlines()])
    return text

def get_lms_assignments():
    if not USER_ID: return
    update_time = arrow.now('Asia/Seoul').format('YYYY-MM-DD HH:mm')
    study_url = "https://eclass.kunsan.ac.kr/Study.do?cmd=viewStudyMyClassroom&boardInfoDTO.boardInfoGubun=myclassroom"

    with sync_playwright() as p:
        # 서버용이므로 headless=True, slow_mo 제거
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto("https://eclass.kunsan.ac.kr/Main.do?cmd=viewHome", wait_until="domcontentloaded")
            page.fill("#id", USER_ID)
            page.fill("#pw", USER_PW)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")

            cal = Calendar()
            seen_tasks = set()
            current_idx = 0

            while True:
                page.goto(study_url, wait_until="domcontentloaded")
                page.wait_for_selector("li.work", timeout=20000)
                items = page.query_selector_all("li.work div.content")
                
                if current_idx >= len(items): break
                
                target = items[current_idx]
                title = target.get_attribute("title") or ""
                spans = target.query_selector_all("span")
                
                if len(spans) < 2 or ("work_" in title and len(title) < 10):
                    current_idx += 1
                    continue

                subject = spans[0].inner_text().strip()
                date_text = spans[-1].inner_text().strip()
                event_name = f"[{subject}] {title}"
                
                if event_name in seen_tasks:
                    current_idx += 1
                    continue

                task_description = "상세 내용을 가져오지 못했습니다."
                try:
                    target.scroll_into_view_if_needed()
                    page.evaluate("(el) => el.click()", target)
                    page.wait_for_selector(".cont.pb0, .board_view_area", timeout=8000)
                    
                    content_element = page.query_selector(".cont.pb0") or page.query_selector(".board_view_area")
                    if content_element:
                        task_description = clean_text(content_element.inner_text())

                except: pass

                dates = re.findall(r"(\d{4}\.\d.2}\.\d{2} \d{2}:\d{2})", date_text)
                if len(dates) == 2:
                    event = Event()
                    event.name = event_name
                    event.begin = arrow.get(dates[0], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    event.end = arrow.get(dates[1], "YYYY.MM.DD HH:mm").replace(tzinfo='Asia/Seoul')
                    event.description = f"과목: {subject}\n\n[과제 내용]\n{task_description}\n\n최신화 시간: {update_time}"
                    
                    for d in [-3, -1]:
                        t_time = event.end.shift(days=d).replace(hour=9, minute=0, second=0)
                        event.alarms.append(DisplayAlarm(trigger=t_time - event.begin))
                    cal.events.add(event)
                    seen_tasks.add(event_name)

                current_idx += 1

            with open('ksnu_assignments.ics', 'w', encoding='utf-8') as f:
                f.write(cal.serialize())

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    get_lms_assignments()
