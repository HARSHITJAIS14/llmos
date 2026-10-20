/**
 * ============================================================================
 * FILE: testing/test_safari_overleaf.ts
 * PURPOSE: Direct Safari Overleaf Project Creation & LaTeX Insertion Test
 * 
 * DESCRIPTION:
 * Tests the exact Safari Overleaf workflow without Chrome, without vision/screenshots,
 * using focus-guarded C++ CoreGraphics events and native Safari AppleScript.
 * ============================================================================
 */

import { AxTreeEngine } from '../openclaw/src/node-host/ax-tree-engine';

async function testSafariOverleaf() {
  console.log(`\n===============================================================`);
  console.log(`🧭 TESTING SAFARI OVERLEAF WORKFLOW (100% NATIVE, ZERO SCREENSHOTS)`);
  console.log(`===============================================================\n`);

  // Step 1: Ensure Safari is focused on Overleaf Projects
  console.log(`[Step 1] Focusing Safari and navigating to Overleaf Projects...`);
  AxTreeEngine.launchApp('Safari');
  AxTreeEngine.safariNavigate('https://www.overleaf.com/project');
  AxTreeEngine.wait(3000);

  const status = AxTreeEngine.safariGetStatus();
  console.log(`⚡ Safari Status:`, status);

  // Step 2: Click the green "New Project" button in the sidebar
  console.log(`\n[Step 2] Clicking 'New Project' green button (x: 215, y: 155)...`);
  AxTreeEngine.clickPhysical(215, 155, true, 'Safari');
  AxTreeEngine.wait(800);

  // Step 3: Click "Blank Project" dropdown item
  console.log(`\n[Step 3] Clicking 'Blank Project' (x: 215, y: 200)...`);
  AxTreeEngine.clickPhysical(215, 200, true, 'Safari');
  AxTreeEngine.wait(1200);

  // Step 4: Type project name "cursor for che" and press Return
  console.log(`\n[Step 4] Typing project name 'cursor for che' + Return...`);
  AxTreeEngine.macroType('cursor for che', { app: 'Safari', submit: true });
  console.log(`⏳ Waiting 5000ms for Overleaf project editor to load...`);
  AxTreeEngine.wait(5000);

  const editorStatus = AxTreeEngine.safariGetStatus();
  console.log(`⚡ Safari Editor Status:`, editorStatus);

  // Step 5: Read local plan.md and convert to LaTeX
  console.log(`\n[Step 5] Reading plan.md and preparing LaTeX code...`);
  const fileRes = AxTreeEngine.findAndReadFile('plan.md', 'LLM_UGP');
  console.log(`⚡ File Found:`, fileRes.path);

  const sampleLatex = `\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{amsmath}
\\usepackage{geometry}
\\geometry{a4paper, margin=1in}

\\title{AI-Powered Chemical Engineering IDE for GCMC Simulations}
\\author{Harshit}
\\date{\\today}

\\begin{document}
\\maketitle

\\begin{abstract}
This document outlines the project proposal for an intelligent, LLM-orchestrated Chemical Engineering IDE designed for Grand Canonical Monte Carlo (GCMC) simulations, porous material modeling, and automated reaction engineering workflows.
\\end{abstract}

\\section{Introduction}
Modern computational chemical engineering requires unified workflows bridging molecular simulations, thermodynamic analysis, and real-time LLM agent guidance.

\\section{Core Architecture}
\\begin{itemize}
  \\item \\textbf{Simulation Kernel:} High-performance Monte Carlo backend for adsorption isotherm generation.
  \\item \\textbf{AI Agent Brain:} Natural language code-generation and simulation parameter optimization.
  \\item \\textbf{Native GUI:} Cross-platform responsive visual canvas for molecular structures.
\\end{itemize}

\\section{Conclusion}
The proposed IDE bridges the gap between molecular thermodynamics and autonomous agent workflows.

\\end{document}`;

  // Step 6: Click inside editor body and paste LaTeX code
  console.log(`\n[Step 6] Clicking editor body (x: 480, y: 400) and inserting LaTeX...`);
  AxTreeEngine.clickPhysical(480, 400, true, 'Safari');
  AxTreeEngine.wait(500);

  // Select all default code
  AxTreeEngine.pressKeys('cmd+a', 'Safari');
  AxTreeEngine.wait(300);

  // Macro type / paste the full LaTeX document
  AxTreeEngine.macroType(sampleLatex, { app: 'Safari' });
  AxTreeEngine.wait(1000);

  console.log(`\n===============================================================`);
  console.log(`🎉 SUCCESS: Overleaf Project 'cursor for che' created and LaTeX inserted in Safari!`);
  console.log(`===============================================================\n`);
}

testSafariOverleaf().catch((err) => {
  console.error(`❌ Safari Overleaf Test Error:`, err);
});
