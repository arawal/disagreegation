#!/usr/bin/env python3
"""Builds docs/Data_Sources_and_How_To_Redo_This.pdf from the content below."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem, HRFlowable
)

OUT = "docs/Data_Sources_and_How_To_Redo_This.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=16, spaceAfter=10, spaceBefore=18))
styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=12.5, spaceAfter=6, spaceBefore=12,
                          textColor=colors.HexColor("#1a3a5c")))
styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=8))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=11,
                          textColor=colors.HexColor("#444444")))
styles.add(ParagraphStyle(name="Mono", parent=styles["Normal"], fontName="Courier", fontSize=8.3,
                          leading=11, textColor=colors.HexColor("#0b3d91"), spaceAfter=8))
styles.add(ParagraphStyle(name="Title0", parent=styles["Title"], fontSize=19, spaceAfter=4))
styles.add(ParagraphStyle(name="Subtitle", parent=styles["Normal"], fontSize=10.5, leading=14,
                          textColor=colors.HexColor("#555555"), spaceAfter=18))

def P(text, style="Body"):
    return Paragraph(text, styles[style])

def table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t

story = []

story.append(P("Georgia Seismic Design Data: Where It Came From and How to Redo It", "Title0"))
story.append(P("A plain-English guide for anyone who needs to understand, check, or reproduce this "
               "dataset — no programming background required.", "Subtitle"))
story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 10))

story.append(P("1. What this dataset is", "H2"))
story.append(P(
    "This project fills in a table of earthquake design numbers for about 213,000 points spread "
    "evenly across the state of Georgia, roughly one point every 800 meters. The table follows the "
    "AASHTO (American Association of State Highway and Transportation Officials) 9th Edition bridge "
    "design standard. For each point, the table needs two kinds of numbers:"
))
story.append(ListFlowable([
    ListItem(P("<b>Design values</b> &mdash; the official shaking numbers an engineer plugs into a bridge "
               "design (As, Sd1, PGA, Ss, S1, Sds, and a design category letter).")),
    ListItem(P("<b>The &ldquo;characteristic earthquake&rdquo;</b> &mdash; in plain terms, the single "
               "most representative earthquake (how big, and how far away) behind the shaking risk at "
               "that point. The table calls these &ldquo;Modal Mw&rdquo; (size) and &ldquo;Modal R&rdquo; "
               "(distance).")),
], bulletType="bullet", start="circle"))

story.append(P("2. Where the numbers come from", "H2"))
story.append(P(
    "Both kinds of numbers come from free, public tools run by the <b>US Geological Survey (USGS)</b>, "
    "the US government's earth-science agency. No number here was guessed or estimated by AI. Every "
    "number traces back to one of these two official USGS tools, running USGS's current national "
    "earthquake hazard model (the &ldquo;2018 update&rdquo;, the standard one at the time this was built)."
))
story.append(table([
    ["Tool", "What it gives you", "Website people can use by hand"],
    ["AASHTO Design Maps", "Design values (As, Sd1, PGA, Ss, S1, Sds, design category)",
     "earthquake.usgs.gov/ws/building-codes"],
    ["Hazard Disaggregation", "The characteristic earthquake (Modal Mw and Modal R)",
     "earthquake.usgs.gov/nshmp/hazard/disagg"],
], widths=[1.5 * inch, 2.5 * inch, 2.4 * inch]))
story.append(Spacer(1, 8))

story.append(P("3. The settings that were used", "H2"))
story.append(P(
    "Every request to USGS used the same settings, so the whole table is consistent:"
))
story.append(ListFlowable([
    ListItem(P("<b>Hazard level:</b> a 1,033-year return period &mdash; the standard AASHTO bridge level, "
               "sometimes described as &ldquo;about a 7% chance in 75 years.&rdquo;")),
    ListItem(P("<b>What is measured:</b> PGA, &ldquo;peak ground acceleration&rdquo; &mdash; roughly, "
               "how hard the ground shakes.")),
    ListItem(P("<b>Soil stiffness (&ldquo;Vs30&rdquo;):</b> each AASHTO Site Class stands for a different "
               "soil stiffness. The table below is what USGS uses for each letter; this project ran the "
               "stiffer-soil values (530, 260 and 150) plus 760, which doubles as the stiff end of Class B.")),
], bulletType="bullet", start="circle"))
story.append(table([
    ["Site Class", "A", "B", "C", "D", "E"],
    ["Soil stiffness (Vs30, m/s)", "1500", "1080", "530", "260", "150"],
    ["Run in this project?", "no (see Sec. 7)", "partly (via 760)", "yes", "yes", "yes"],
], widths=[1.9 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch]))
story.append(Spacer(1, 8))

story.append(P("4. How the numbers were actually collected", "H2"))
story.append(P(
    "The ordinary USGS website only answers one location at a time. This project needed answers for "
    "roughly 213,000 locations, times several soil classes. That is far too slow to do by hand. "
    "Luckily, both USGS tools also work as an &ldquo;API&rdquo;: a plain web address that hands back "
    "the numbers directly, instead of showing a page. A short program can send that same web address "
    "thousands of times in a row, automatically."
))
story.append(P(
    "A program in this folder sent one such request per location and saved each answer. Here is what "
    "one request looks like. Paste it into a browser to see the real answer for that one spot "
    "(Atlanta, Site Class D):"
))
story.append(P(
    "https://earthquake.usgs.gov/ws/building-codes/aashto-2009/calculate?"
    "latitude=33.75&amp;longitude=-84.39&amp;siteClass=D", "Mono"))
story.append(P("And the matching request for the characteristic earthquake (same spot, soil stiffness 260, "
               "1,033-year level):", "Body"))
story.append(P(
    "https://earthquake.usgs.gov/ws/nshmp/conus-2018.R1/dynamic/disagg/"
    "-84.39/33.75/260/1033?imt=PGA", "Mono"))

story.append(P("5. A necessary shortcut, and its small tradeoff", "H2"))
story.append(P(
    "The characteristic-earthquake tool is slow, several seconds per request, and must be asked once "
    "per soil class. Asking it directly at all 213,000 points, for every soil class, would have taken "
    "many days per class just waiting on that one tool. So the program took a shortcut: it asked the "
    "tool directly at a well-spread sample of points, then estimated the points in between from their "
    "nearest already-answered neighbors. Think of reading a value between two marked points on a graph. "
    "It only estimated where nearby points already agreed closely. Anywhere they did not agree, it asked "
    "more points nearby until they did."
))
story.append(P(
    "To check this shortcut, the program re-asked USGS directly for 300 random estimated points per "
    "soil class, then compared the two answers. Across all four soil classes, 96% to 97% of those "
    "checks matched USGS's real answer closely (earthquake size within 0.1, distance within 5 km). "
    "Almost all the rest still named the right earthquake, just with the distance figure one step off. "
    "A small handful showed a real difference, right at a boundary where the governing earthquake "
    "switches from a nearby small one to a distant large one. The design-value numbers (As, Sd1, PGA, "
    "Ss, S1, Sds) never use this shortcut. The program asked for every one of the 213,000-plus points "
    "directly."
))

story.append(P("6. What is in this folder", "H2"))
story.append(table([
    ["File / folder", "What it is"],
    ["output/", "The finished tables. See Section 8 for which file to use."],
    ["aashto_batch.py", "Asks the AASHTO Design Maps tool for a list of points, one soil class "
                        "at a time or several at once."],
    ["disagg_adaptive.py", "Asks the Disaggregation tool for the characteristic earthquake, using the "
                           "sampling shortcut from Section 5, for one soil class at a time."],
    ["fill_table.py", "Combines the two tools' answers into one spreadsheet, in the original table's "
                      "layout."],
    ["usgs_client.py", "Shared plumbing: makes sure requests don't go to USGS faster than it allows, "
                       "and automatically waits and retries if USGS is briefly unavailable."],
    ["run_*.sh, watchdog*.sh", "Convenience scripts that run the above in the right order for hours or "
                               "days at a time without someone watching, restarting automatically if "
                               "anything stops partway."],
    ["test_disagg_adaptive.py", "Automated checks confirming the shortcut in Section 5 behaves correctly."],
], widths=[2.1 * inch, 4.8 * inch]))
story.append(Spacer(1, 8))

story.append(P("7. Step by step: how to redo this in the future", "H2"))
story.append(P(
    "Anyone with this folder and the two Python programs below, plus the Georgia coordinate list "
    "(a spreadsheet of longitude, latitude, county, and existing soil data &mdash; the same list this "
    "project started from), can redo any part of this or extend it to a soil class not yet run "
    "(Class A, soil stiffness 1500, or a full statewide Class B at 1080)."
))
story.append(ListFlowable([
    ListItem(P("<b>Install Python 3</b> on the computer doing the work. No other setup is required; "
               "the scripts use only Python's built-in tools.")),
    ListItem(P("<b>Ask for the characteristic earthquake</b> for a soil class, for example Class A:")),
], bulletType="1", start=1))
story.append(P(
    "python3 disagg_adaptive.py your_coordinate_list.csv --out disagg_out_A --vs30 1500 --spot-check 300",
    "Mono"))
story.append(ListFlowable([
    ListItem(P("<b>Ask for the design values</b> for the same soil class, for every point:")),
], bulletType="1", start=3))
story.append(P(
    "python3 aashto_batch.py your_coordinate_list.csv --out aashto_out_A --site-classes A",
    "Mono"))
story.append(ListFlowable([
    ListItem(P("<b>Combine the two</b> into one finished spreadsheet:")),
], bulletType="1", start=4))
story.append(P(
    "python3 fill_table.py your_coordinate_list.csv --force-class A --trim-to-force-class "
    "--aashto aashto_out_A/aashto_values.csv --disagg disagg_out_A/disagg_grid.csv",
    "Mono"))
story.append(P(
    "Expect each soil class to take somewhere between several hours and about a day, because USGS "
    "limits how fast any one computer may ask it questions. The scripts already wait and retry on "
    "their own when that happens &mdash; it is normal to start a step and leave it running unattended, "
    "and it will pick back up on its own if it is ever interrupted, re-using what it already collected "
    "instead of starting over.", "Small"
))

story.append(P("8. Which finished file to use", "H2"))
story.append(P(
    "Inside <font face='Courier'>output/</font>, use the files named "
    "<font face='Courier'>..._forced_class_X_trimmed.csv</font> (X = C, D, or E). These are the clean, "
    "self-consistent tables. Every point in one of these files used that one soil class for both the "
    "design values and the characteristic earthquake, with no mixing. Hand one of these to an engineer. "
    "The earlier files named <font face='Courier'>..._filled.csv</font> and "
    "<font face='Courier'>..._own_class.csv</font> use each point's own real soil class for the design "
    "values, but one fixed soil stiffness (760) for the characteristic earthquake everywhere. Treat "
    "those as a quick first look, not a final answer, except where a point's real class is already "
    "close to 760.", "Body"
))

story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc")))
story.append(Spacer(1, 4))
story.append(P(
    "Every number in this dataset can be independently re-checked at any time by typing the website "
    "addresses above (with different coordinates) directly into a web browser &mdash; no special "
    "access or account is needed; these are free public USGS tools.", "Small"
))

doc = SimpleDocTemplate(OUT, pagesize=letter,
                         leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                         topMargin=0.7 * inch, bottomMargin=0.7 * inch)
doc.build(story)
print(f"wrote {OUT}")
