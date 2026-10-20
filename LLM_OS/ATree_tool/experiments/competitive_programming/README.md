# Competitive Programming & Codeforces 1117 Experiment

**Task**: Open the `Competitive Programming` folder in VS Code and solve problems A & B of Codeforces Round 1117 (Div. 2).

### Disambiguation First
- Discovered two candidate folders on the filesystem:
  1. `/Users/harshit/Desktop/Competitive Programming`
  2. `/Users/harshit/Aspire/Quick/Competitive Programming`
- Prompted user for disambiguation; user confirmed `/Users/harshit/Desktop/Competitive Programming`.

### Actions Executed
1. **VS Code Automation**: Invoked `tasks/open_vscode_folder.py` to activate VS Code, invoke `Cmd+O`, navigate to `/Users/harshit/Desktop/Competitive Programming`, and confirm opening the workspace with full state-diff tracking.
2. **Problem Analysis & Implementation**:
   - **Problem 1117A (Best Subsegment)**:
     - *Mathematical Insight*: The maximum arithmetic mean is $\max(a)$. The subsegment achieving this mean must consist solely of $\max(a)$. Hence, the problem reduces to finding the longest contiguous run of $\max(a)$.
     - *Complexity*: Time $O(n)$, Space $O(n)$.
     - *File*: `1117A_best_subsegment.cpp`
   - **Problem 1117B (Emotes)**:
     - *Mathematical Insight*: To maximize happiness with at most $k$ consecutive presses of the highest emote $M_1$, use $M_1$ $k$ times followed by the second highest $M_2$ $1$ time. Block size is $k + 1$ with value $k \cdot M_1 + M_2$. Remainder $m \pmod{k + 1}$ presses use $M_1$.
     - *Complexity*: Time $O(n \log n)$ / $O(n)$, Space $O(n)$.
     - *File*: `1117B_emotes.cpp`
3. **Verification**: Compiled with `clang++ -std=c++17` and verified on all sample test cases.
4. **Editor Focus**: Opened the solution in the active VS Code workspace editor via Quick Open (`Cmd+P`).
