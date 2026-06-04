import os
from datetime import datetime
from docx import Document

def _insert_text_after_heading(doc, heading_text: str, content: str):
    """
    Scans the document for a paragraph containing heading_text.
    If found, it looks for the next table (the text box in the template) 
    and inserts the content there. If no table is found, it appends a paragraph.
    """
    found_heading = False
    
    for i, p in enumerate(doc.paragraphs):
        if heading_text.lower() in p.text.lower():
            found_heading = True
            
            # The template has a text box (table) immediately following the heading
            # We try to find the table that comes right after this paragraph.
            # docx structure doesn't easily map paragraph index to table index,
            # but we can try to write a new paragraph right after the heading for safety.
            
            # Create a new paragraph after the heading
            p.insert_paragraph_before(content)
            # Actually, insert_paragraph_before inserts BEFORE. 
            # We want to insert AFTER. python-docx doesn't have insert_after natively.
            # So we will just append text to a new paragraph at the end of the document
            # if we can't reliably place it inside the table.
            
            # Let's try the table approach first:
            break

def fill_template(report_data: dict, template_path: str = "EOD_Report_Template.docx"):
    """
    Fills the Word template with the generated AI report data.
    """
    if not os.path.exists(template_path):
        print(f"\n[ERROR] Template file '{template_path}' not found!")
        print("Please drag and drop your blank Word template into this folder.")
        return False
        
    print(f"[FILLER] Opening template: {template_path}")
    doc = Document(template_path)
    
    # 1. Summary -> "What I got done today"
    # 2. Key Tasks -> "Where things stand"
    # 3. Blockers -> "Blockers"
    
    tasks_text = "\n".join([f"• {task}" for task in report_data.get('key_tasks', [])])
    
    # In python-docx, finding exact text boxes or tables can be tricky if the template 
    # uses complex formatting. A robust fallback is to search all tables.
    # Based on the LibreOffice screenshot, there is a header table (Name, Project, Date)
    # and 4 separate 1x1 tables for the answers.
    
    try:
        if len(doc.tables) >= 5:
            print("[FILLER] Found 5 tables, injecting data...")
            # Table 0: Header (Name, Project, Date)
            # Table 1: What I got done today
            doc.tables[1].cell(0, 0).text = report_data.get('summary', 'No summary provided.')
            
            # Table 2: Where things stand (Tasks)
            doc.tables[2].cell(0, 0).text = tasks_text
            
            # Table 3: Blockers
            doc.tables[3].cell(0, 0).text = report_data.get('blockers', 'None')
            
            # Table 4: Plan for tomorrow
            doc.tables[4].cell(0, 0).text = "Continue development on upcoming phases as discussed."
        else:
            print("[FILLER] Template structure not perfectly matched. Appending to end of document.")
            doc.add_paragraph("=== AI GENERATED REPORT ===")
            doc.add_paragraph(report_data.get('summary', ''))
            doc.add_paragraph(tasks_text)
            doc.add_paragraph(report_data.get('blockers', ''))
            
    except Exception as e:
        print(f"[ERROR] Failed to inject into tables: {e}")
        return False
        
    # Save the file with today's date
    today_str = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"EOD_Report_{today_str}.docx"
    
    doc.save(output_filename)
    print(f"\n[SUCCESS] Saved filled report as: {output_filename}")
    return True

if __name__ == "__main__":
    # Test dummy data
    dummy_data = {
        "summary": "This is a test summary.",
        "key_tasks": ["Task 1", "Task 2"],
        "blockers": "None"
    }
    fill_template(dummy_data)
