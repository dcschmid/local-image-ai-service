import { test, expect } from '@playwright/test';
test('both trained Anima styles restore reproducible presets and guide links',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const catalog=await(await page.request.get('/studio/api/catalog')).json();
 const variants=[['anima-psx',.9,'psx-character','psx'],['anima-lowpoly',.75,'anima3d-diorama','l0wp0ly']];
 for(const [model,strength,recipe,trigger] of variants){
  const entry=catalog.models.find(m=>m.id===model);expect(entry.installed).toBeTruthy();expect(entry.base_model).toBe('anima');expect(entry.lora_strength).toBe(strength);
  const recipes=catalog.recipes.filter(r=>r.model===model);expect(recipes).toHaveLength(3);
  for(const r of recipes){const sample=catalog.examples[r.id];expect(sample.model).toBe(model);expect(sample.lora_strength).toBe(strength);expect(sample.prompt).toContain(trigger);const asset=await page.request.get(sample.url);expect(asset.ok()).toBeTruthy();}
  await page.goto('/studio/?recipe='+recipe+'#workspace');
  await expect(page.locator('#model')).toHaveValue(model);await expect(page.locator('#recipe')).toHaveValue(recipe);
  await expect(page.locator('#subject')).toHaveValue(catalog.examples[recipe].inputs.subject);
  await expect(page.locator('#recipe-preview')).toContainText(trigger);await expect(page.locator('#recipe-preview')).toContainText('35 steps · CFG 4.5');
  await expect(page.locator('#seed')).toHaveValue(String(catalog.examples[recipe].seed));await expect(page.locator('#pixel-fields')).toBeHidden();
  const response=await page.request.post('/studio/api/compose',{data:{...catalog.examples[recipe].inputs,model,quality:'standard',seed:42}});
  expect(response.ok()).toBeTruthy();const prepared=await response.json();expect(prepared.prompt).toBe(catalog.examples[recipe].prompt);
  await page.locator('#aspect-ratio').selectOption('16:9');await expect(page.locator('#recipe-preview')).toContainText('1024x576');
  await page.locator('#workflow').selectOption('free');await expect(page.locator('#prompt')).toBeVisible();await expect(page.locator('#cfg')).toBeEnabled();
 }
 await page.goto('/studio/lowpoly-guide/');await expect(page.getByRole('heading',{name:'Build a polygon world.'})).toBeVisible();
 await expect(page.locator('.recipe-card')).toHaveCount(6);await expect(page.locator('html')).toHaveAttribute('lang','en');
 const link=page.locator('a[href="/studio/?recipe=psx-prop#workspace"]');await link.click();await expect(page.locator('#recipe')).toHaveValue('psx-prop');
 await page.setViewportSize({width:390,height:844});await page.locator('#recipe').focus();await page.keyboard.press('Tab');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'test-results/lowpoly-mobile.png'});
 expect(errors).toEqual([]);
});
