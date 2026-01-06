import streamlit as st

def render_navbar(current_page: int):
    LINE_COLOR = "#ff5c5c"
    LINE_BG = "#dddddd"
    TOTAL_PAGES = 3
    CIRCLE_DIAMETER = 40  # px
    CONTAINER_WIDTH_PX = 600  # must match CSS max-width below

    PAGES = [
        {"name": "1", "index": 1},
        {"name": "2", "index": 2},
        {"name": "3", "index": 3},
    ]

    # Compute progress percent (0 to 100)
    progress_percent = 0
    if TOTAL_PAGES > 1:
        step_width = 100 / (TOTAL_PAGES - 1)
        progress_percent = step_width * (current_page - 1)
    progress_percent = max(0, min(progress_percent, 100))

    # Calculate pixel width for progress line
    available_width = CONTAINER_WIDTH_PX - CIRCLE_DIAMETER  # space between circle centers
    progress_width_px = (progress_percent / 100) * available_width

    html = f"""
    <style>
        .navbar-container {{
            position: relative;
            height: 80px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 40px;
            width: 100%;
            max-width: {CONTAINER_WIDTH_PX}px;
        }}

        .navbar-line-bg {{
            position: absolute;
            top: 50%;
            left: {CIRCLE_DIAMETER / 2}px;
            right: {CIRCLE_DIAMETER / 2}px;
            height: 6px;
            background-color: {LINE_BG};
            border-radius: 5px;
            z-index: 0;
            transform: translateY(-50%);
        }}

        .navbar-line-progress {{
            position: absolute;
            top: 50%;
            left: {CIRCLE_DIAMETER / 2}px;
            height: 6px;
            width: {progress_width_px}px;
            background-color: {LINE_COLOR};
            border-radius: 5px;
            z-index: 1;
            transform: translateY(-50%);
        }}

        .navbar-circles {{
            display: flex;
            justify-content: space-between;
            width: 100%;
            padding: 0 {CIRCLE_DIAMETER / 2}px;
            z-index: 2;
        }}

        .circle {{
            width: {CIRCLE_DIAMETER}px;
            height: {CIRCLE_DIAMETER}px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 18px;
            border: 2px solid {LINE_COLOR};
            background-color: white;
            color: {LINE_COLOR};
            user-select: none;
        }}

        .circle.active {{
            background-color: {LINE_COLOR};
            color: white;
        }}
    </style>

    <div class="navbar-container">
        <div class="navbar-line-bg"></div>
        <div class="navbar-line-progress"></div>
        <div class="navbar-circles">
    """

    for page in PAGES:
        is_active = page["index"] <= current_page
        active_class = "circle active" if is_active else "circle"
        html += f'<div class="{active_class}">{page["name"]}</div>'

    html += """
        </div>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)
