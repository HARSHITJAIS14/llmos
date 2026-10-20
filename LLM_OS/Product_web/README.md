# LLM OS Promotional Website

This is the promotional website for LLM OS, built with a premium "Modern Product Launch" aesthetic using pure **Vanilla HTML, CSS, and JavaScript**.

Because it is built without a heavy framework, it is blazing fast and requires zero build steps or compilation. 

## How to Run It

You have a few easy options to view the website locally:

### Option 1: Open Directly in Browser (Easiest)
Simply double-click the `index.html` file in your file explorer, or run this command in your terminal:
```bash
open index.html
```
*(Note: Some scroll animations might look slightly better on a local server depending on your browser's security policies for local files, but it will mostly work perfectly!)*

### Option 2: Run a Simple Python Server (Recommended)
If you have Python installed on your Mac, you can spin up a local server in 2 seconds. Open your terminal in this `Product_web` directory and run:
```bash
python3 -m http.server 8000
```
Then, open your browser and go to: [http://localhost:8000](http://localhost:8000)

### Option 3: Run using Node.js (npx)
If you have Node.js installed, you can use the `serve` package:
```bash
npx serve .
```

## Structure
- `index.html` — The main structure of the page.
- `css/style.css` — The complete design system and responsive styles.
- `js/animations.js` — The IntersectionObserver logic for the premium fade-in/slide-up scroll animations.

## Swapping Images
Currently, the site uses placeholder image URLs (like `https://placehold.co/...`) that match the exact aspect ratios of the design. 

When you have your real assets (UI mockups, videos, etc.) ready, simply open `index.html` and replace the `src` attribute of the `<img>` tags with the paths to your real images!
