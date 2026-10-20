import os
import sys
import time
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.harness_logger import HarnessLogger
from utils.dfs_tree import capture_full_dfs_tree, run_agent_cmd

def setup_essay_clipboard(folder_path):
    essay_html_path = os.path.join(folder_path, "essay.html")
    essay_rtf_path = os.path.join(folder_path, "essay.rtf")
    
    essay_content = """<h1>Steve Jobs: The Visionary Who Redefined Technology</h1>

<p>Steve Jobs was not merely a businessman; he was a cultural icon, a visionary, and a pioneer who fundamentally transformed the way we interact with technology. As the co-founder of Apple Inc., Jobs brought an uncompromising emphasis on design, simplicity, and user experience to an industry that was previously dominated by beige boxes and complex interfaces. His life story is a testament to the power of relentless perfectionism and the belief that technology and the liberal arts should intersect.</p>

<h2>Early Life and the Birth of Apple</h2>

<p>Born in 1955 in San Francisco and adopted by Paul and Clara Jobs, Steve grew up in the heart of what would soon become Silicon Valley. After dropping out of Reed College, he teamed up with his friend, Steve Wozniak, a brilliant engineer. In 1976, working out of the Jobs family garage, they founded Apple Computer. Their first significant product, the Apple II, became one of the first highly successful mass-produced microcomputers, catapulting the young company to success.</p>

<p>However, it was the introduction of the Macintosh in 1984 that truly showcased Jobs's vision. The Mac popularized the graphical user interface (GUI) and the mouse, shifting computing from command-line obscurity to an intuitive, visual experience.</p>

<h2>The Triumphant Return and Apple's Renaissance</h2>

<p>In 1997, Apple, struggling and on the brink of bankruptcy, acquired NeXT, bringing Jobs back to the company he founded. What followed is arguably the greatest corporate turnaround in history. Jobs swiftly simplified the product line and introduced the iMac in 1998, a colorful, all-in-one computer that signaled Apple's resurgence.</p>

<p>The 2000s saw a relentless string of innovations:</p>
<ul>
<li><b>The iPod (2001):</b> Revolutionized the music industry by putting "a thousand songs in your pocket."</li>
<li><b>The iPhone (2007):</b> A groundbreaking convergence of an iPod, a mobile phone, and an internet communicator that completely redefined the smartphone.</li>
<li><b>The iPad (2010):</b> Created a new category of mobile computing.</li>
</ul>

<h2>Legacy and Impact</h2>

<p>Steve Jobs passed away in 2011, but his legacy endures. He proved that consumers care deeply about design and that intuitive, beautifully crafted products could change the world. His famous commencement address at Stanford University urged people to "stay hungry, stay foolish," a philosophy that continues to inspire innovators globally. Jobs didn't just build devices; he engineered experiences that reshaped modern life.</p>
"""
    with open(essay_html_path, "w") as f:
        f.write(essay_content)
    
    # Convert to RTF
    subprocess.run(["textutil", "-convert", "rtf", essay_html_path], check=True)
    
    # Load into clipboard as RTF using AppleScript
    applescript_cmd = f'set the clipboard to (read (POSIX file "{essay_rtf_path}") as "RTF ")'
    subprocess.run(["osascript", "-e", applescript_cmd], check=True)
    print("Prepared formatted RTF in the clipboard.")

def find_node(tree, **kwargs):
    """Recursively search for a node matching the kwargs."""
    if not isinstance(tree, dict):
        return None
        
    match = True
    for k, v in kwargs.items():
        if k == "states":
            if not isinstance(tree.get("states"), list) or v not in tree["states"]:
                match = False
                break
        elif k == "native_id":
            if tree.get("native_id", {}).get("value") != v:
                match = False
                break
        elif tree.get(k) != v:
            match = False
            break
            
    if match:
        return tree
        
    for child in tree.get("children", []):
        res = find_node(child, **kwargs)
        if res:
            return res
    return None

def main():
    folder_path = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(folder_path, "workflow_execution.diff.log")
    logger = HarnessLogger(log_path, task_name="Steve Jobs Essay Automation")
    
    # 1. Setup clipboard
    setup_essay_clipboard(folder_path)
    
    # 2. Activate Word safely
    print("Activating Microsoft Word...")
    subprocess.run(["osascript", "-e", 'tell application "Microsoft Word" to reopen', "-e", 'tell application "Microsoft Word" to activate'])
    time.sleep(1) # wait for window animation
    
    # 3. Capture baseline state
    print("Capturing baseline S0...")
    s0 = capture_full_dfs_tree("Microsoft Word")
    if not s0.get("ok"):
        print("Failed to capture state S0:", s0)
        logger.finalize(success=False, notes="Failed to capture S0")
        return
        
    logger.log_initial_state(s0["data"]["tree"], description="Blank Document")
    
    # 4. Paste RTF
    print("Pasting text...")
    run_agent_cmd(["press", "cmd+v"])
    time.sleep(2) # Give it time to paste
    
    s1 = capture_full_dfs_tree("Microsoft Word")
    logger.log_action("Paste Formatted Text", action_details={"keys": "cmd+v"}, new_state=s1["data"]["tree"], description="Pasted the Steve Jobs RTF essay")
    
    # 5. Save Dialog Trigger
    print("Triggering Save Dialog...")
    run_agent_cmd(["press", "cmd+s"])
    
    # 6. Cognitive Loop to wait for save dialog sheet
    s2 = None
    save_textfield = None
    save_button = None
    for attempt in range(10):
        time.sleep(1)
        print(f"Waiting for save panel... attempt {attempt+1}")
        s_current = capture_full_dfs_tree("Microsoft Word")
        if not s_current.get("ok"):
            continue
            
        tree = s_current["data"]["tree"]
        save_textfield = find_node(tree, native_id="saveAsNameTextField")
        save_button = find_node(tree, native_id="OKButton")
        
        if save_textfield and save_button:
            s2 = s_current
            break
            
    if not s2:
        print("Save dialog did not appear or nodes not found.")
        logger.finalize(success=False, notes="Save dialog failed.")
        return
        
    logger.log_action("Trigger Save Dialog", action_details={"keys": "cmd+s"}, new_state=s2["data"]["tree"], description="Wait until saveAsNameTextField appears")
    
    # 7. Name the document and click Save
    print("Setting filename and saving...")
    filename = "Steve_Jobs_Experiment_Formatted"
    tf_ref = save_textfield.get("ref_id")
    btn_ref = save_button.get("ref_id")
    snap_id = s2["data"]["snapshot_id"]
    
    run_agent_cmd(["set-value", tf_ref, filename, "--snapshot", snap_id])
    run_agent_cmd(["click", btn_ref, "--snapshot", snap_id])
    
    # 8. Verify save completion
    time.sleep(2)
    s3 = capture_full_dfs_tree("Microsoft Word")
    logger.log_action("Set Name and Save", action_details={"filename": filename}, new_state=s3["data"]["tree"], description="Set filename and click Save button")
    
    logger.finalize(success=True, notes="Successfully pasted formatted essay and saved.")
    print("Done! Check the workflow_execution.diff.log in the experiment folder.")

if __name__ == "__main__":
    main()
