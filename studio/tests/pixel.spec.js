import { test, expect } from '@playwright/test';
const ids=['pixel-loot','pixel-character','pixel-isometric','pixel-landscape','pixel-creature','pixel-portrait','pixel-vehicle','pixel-dungeon','pixel-character-sheet','pixel-kart-sheet','pixel-prop-sheet'];
test('flux-pixel recipes, examples and guided preview',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const catalog=await(await page.request.get('/studio/api/catalog')).json();
 expect(catalog.models.map(m=>m.id)).toEqual(expect.arrayContaining(['flux-pixel']));
 for(const id of ids){const recipe=catalog.recipes.find(r=>r.id===id);expect(recipe.model).toBe('flux-pixel');}
 for(const id of ids.slice(0,4)){
  const sample=catalog.examples[id];expect(sample.model).toBe('flux-pixel');expect(sample.size).toBe('1024x1024');expect(sample.steps).toBe(20);
  expect((await page.request.get(sample.url)).ok()).toBeTruthy();
  const response=await page.request.post('/studio/api/compose',{data:{...sample.inputs,model:'flux-pixel',quality:sample.quality,seed:sample.seed}});
  expect((await response.json()).prompt).toBe(sample.prompt);
 }
 await page.goto('/studio/#explore');await page.locator('#recipe-model-filter').selectOption('flux-pixel');
 await expect(page.locator('.recipe-card')).toHaveCount(6);
 await expect(page.locator('#recipe-total')).toHaveText('6 of 11 recipes');
 const open=page.locator('[data-recipe-id="pixel-character"]').getByRole('button',{name:'View example:'});
 await open.focus();await page.keyboard.press('Enter');await expect(page.locator('#recipe-example')).toBeVisible();
 await expect(page.locator('#example-settings')).toContainText('1024x1024 · 20 steps · CFG 4 · Seed');
 await page.keyboard.press('Escape');await expect(open).toBeFocused();
 await open.click();await page.locator('#use-preview-example').click();
 await expect(page.locator('#model')).toHaveValue('flux-pixel');
 await expect(page.locator('#recipe')).toHaveValue('pixel-character');
 await expect(page.locator('#recipe-preview')).toContainText('PXART4');
 await page.locator('#subject').fill('a small green frog wearing a tiny hat');
 await expect(page.locator('#recipe-preview')).toContainText('a small green frog wearing a tiny hat');
 await expect(page.locator('#recipe-preview')).toContainText('20 steps');
 await page.locator('#recipe-quality').selectOption('preview');
 await expect(page.locator('#recipe-preview')).toContainText('12 steps');
 await page.locator('#recipe-quality').selectOption('detail');
 await expect(page.locator('#recipe-preview')).toContainText('35 steps');
 await page.locator('#recipe').selectOption('pixel-landscape');
 await expect(page.locator('#recipe-preview')).toContainText('PXART4');
 await page.setViewportSize({width:390,height:840});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'test-results/pixel-mobile.png',fullPage:true});
 expect(errors).toEqual([]);
});
test('pixel guide serves the current recipes',async({page})=>{
 await page.goto('/studio/pixel-guide/');
 await expect(page.getByRole('heading',{name:'Build a little world.'})).toBeVisible();
 await expect(page.locator('.recipe-card')).toHaveCount(4);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
