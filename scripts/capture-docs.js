// Run with mm-playwright run-code --filename scripts/capture-docs.js.
// Use serve-docs-demo.py, never the user's normal image library.
async (page) => {
  await page.waitForFunction(() => document.querySelector('#health')?.textContent === 'Documentation demo · public examples');
  await page.setViewportSize({ width: 1600, height: 1320 });
  await page.locator('#recipe').selectOption('lowpoly-anything');
  await page.getByRole('button', { name: 'Use example', exact: true }).click();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => document.querySelector('#result').complete && document.querySelector('#result').naturalWidth > 0);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: 'docs/images/studio-create.webp', type: 'webp', quality: 88, animations: 'disabled' });
  for (const section of ['explore', 'library']) {
    await page.locator('#' + section).scrollIntoViewIfNeeded();
    await page.waitForFunction((id) => Array.from(document.querySelectorAll('#' + id + ' img')).every(image => image.complete && image.naturalWidth > 0), section);
    await page.locator('#' + section).screenshot({ path: `docs/images/studio-${section}.webp`, type: 'webp', quality: 88, animations: 'disabled' });
  }
  return { screenshots: ['studio-create.webp', 'studio-explore.webp', 'studio-library.webp'], publicImages: await page.locator('#gallery .card').count() };
}
