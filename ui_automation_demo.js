const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: false }); // Show browser for demo
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('http://localhost:8501/#27d5d9aa');

    // Click "Browse Files" and upload file
    const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser'),
        page.getByTestId('stBaseButton-secondary').click(),
    ]);
    await fileChooser.setFiles('146464652-AA-036007-001.pdf');

    // Wait for processing to start and then finish
    await page.getByText('Processing PDF and extracting').waitFor();

    // Wait for the results to appear
    await page.getByText('Drawing and Extracted Information').waitFor({ state: 'visible', timeout: 90000 });

    // Give the page a moment to fully render
    await page.waitForTimeout(2000);

    // Debug: Log all images on the page
    const images = await page.$$('img');
    console.log('Found images:', images.length);
    for (const img of images) {
        const src = await img.getAttribute('src');
        const alt = await img.getAttribute('alt');
        console.log('Image:', { src, alt });
    }

    // Scroll to the Material section
    const materialSection = page.getByText('Material').first();
    await materialSection.waitFor({ state: 'attached', timeout: 30000 });
    await page.evaluate(() => {
        const materialElements = Array.from(document.querySelectorAll('*')).filter(el =>
            el.textContent && el.textContent.trim() === 'Material'
        );
        if (materialElements.length > 0) {
            materialElements[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
    await page.waitForTimeout(2000);

    // Try to find and click the help icon, but don't fail if not found
    try {
        const helpIcon = page.locator('img[alt*="help"]').first();
        await helpIcon.waitFor({ state: 'attached', timeout: 5000 });
        await page.evaluate(() => {
            const helpImages = Array.from(document.querySelectorAll('img')).filter(img =>
                img.alt && img.alt.toLowerCase().includes('help')
            );
            if (helpImages.length > 0) {
                helpImages[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
        await helpIcon.click();
        await page.waitForTimeout(2000);
    } catch (error) {
        console.log('Help icon not found, continuing...');
    }

    // Scroll to and expand Source References
    const sourceRefs = page.getByRole('group').filter({ hasText: 'Source References "6" & 8"' });
    await sourceRefs.waitFor({ state: 'attached', timeout: 30000 });
    await page.evaluate((selector) => {
        const element = document.querySelector(selector);
        if (element) element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, '[role="group"]');
    await sourceRefs.locator('summary').click();
    await page.waitForTimeout(3000); // Longer pause after expanding
    // Collapse Source References
    await sourceRefs.locator('summary').click();
    await page.waitForTimeout(3000); // Longer pause after collapsing

    // Scroll to and click Debug Info
    const debugInfo = page.locator('span').filter({ hasText: '🔍 Debug Info (Raw Outputs)' });
    await debugInfo.waitFor({ state: 'attached', timeout: 30000 });
    await page.evaluate((selector) => {
        const element = document.querySelector(selector);
        if (element) element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 'span');
    await debugInfo.click();
    await page.waitForTimeout(3000); // Longer pause after expanding
    // Collapse Debug Info
    await debugInfo.click();
    await page.waitForTimeout(3000); // Longer pause after collapsing

    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));

    await page.waitForTimeout(5000); // Longer final pause before closing
    await browser.close();
})();
