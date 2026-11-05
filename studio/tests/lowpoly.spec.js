import { test, expect } from '@playwright/test';
test('MOSS supplies all low-poly presets while retired Anima styles disappear',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const catalog=await(await page.request.get('/studio/api/catalog')).json();
 expect(catalog.models.map(m=>m.id)).toEqual(['moss','anima','flux-pixel','z-image','z-image-turbo']);
 expect(catalog.recipes).toHaveLength(72);
 const recipes=catalog.recipes.filter(r=>r.category==='lowpoly');expect(recipes).toHaveLength(12);
 for(const recipe of recipes){
  expect(recipe.model).toBe('moss');const sample=catalog.examples[recipe.id];expect(sample.model).toBe('moss');
  expect((await page.request.get(sample.url)).ok()).toBeTruthy();
  const response=await page.request.post('/studio/api/compose',{data:{...sample.inputs,quality:sample.quality,seed:sample.seed}});
  expect(response.ok()).toBeTruthy();expect((await response.json()).prompt).toBe(sample.prompt);
 }
 await page.goto('/studio/?recipe=lowpoly-vehicle#workspace');
 await expect(page.locator('#model')).toHaveValue('moss');await expect(page.locator('#recipe')).toHaveValue('lowpoly-vehicle');
 await expect(page.locator('#subject')).toHaveValue(catalog.examples['lowpoly-vehicle'].inputs.subject);
 await expect(page.locator('#modeling-asset')).toHaveValue('vehicle');
 await expect(page.locator('#recipe-preview')).toContainText('CFG 3');
 await page.locator('#recipe-quality').selectOption('standard');
 await expect(page.locator('#recipe-preview')).toContainText('50 steps · CFG 3');
 await page.locator('#aspect-ratio').selectOption('16:9');await expect(page.locator('#recipe-preview')).toContainText('1024x576');
 await page.goto('/studio/lowpoly-guide/');
 await expect(page.getByRole('heading',{name:'Build a polygon world.'})).toBeVisible();
 await expect(page.locator('.recipe-card')).toHaveCount(9);await expect(page.locator('html')).toHaveAttribute('lang','en');
 await expect(page.locator('main')).not.toContainText('Anima PSX');
 await page.locator('a[href="/studio/?recipe=lowpoly-prop#workspace"]').click();
 await expect(page.locator('#model')).toHaveValue('moss');await expect(page.locator('#recipe')).toHaveValue('lowpoly-prop');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'test-results/lowpoly-moss-mobile.png'});
 expect(errors).toEqual([]);
});

test('general motifs and track overviews use MOSS without a fixed asset type',async({page})=>{
 await page.goto('/studio/?recipe=lowpoly-anything#workspace');
 await expect(page.locator('#model')).toHaveValue('moss');
 await expect(page.locator('#modeling-fields')).toBeHidden();
 await page.locator('#subject').fill('a floating crystal cave');
 await expect(page.locator('#recipe-preview')).toContainText('a floating crystal cave');
 await expect(page.locator('#recipe-preview')).not.toContainText('A-pose');
 await page.locator('#recipe').selectOption('lowpoly-track-overview');
 await page.locator('#example').click();
 await expect(page.locator('#subject')).toHaveValue(/kart circuit/);
 await expect(page.locator('#recipe-preview')).toContainText('complete closed driving loop');
 await expect(page.locator('#modeling-fields')).toBeHidden();
 await page.locator('#recipe-quality').selectOption('standard');
 await expect(page.locator('#recipe-preview')).toContainText('1216x832 · 50 steps · CFG 3');
 await page.screenshot({path:'test-results/lowpoly-track-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'test-results/lowpoly-track-mobile.png'});
});
