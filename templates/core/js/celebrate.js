/* Small celebrations and counting numbers. */
/* Small celebrations and counting numbers. Both stay still for people who prefer reduced motion. */
(function(){
  var still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  var COLORS=['#f59e0b','#10b981','#3b82f6','#ec4899','#8b5cf6','#ef4444'];
  window.pqConfetti=function(x,y,n){
    if(still) return; x=x==null?innerWidth/2:x; y=y==null?innerHeight/3:y; n=n||36;
    var layer=document.createElement('div'); layer.setAttribute('aria-hidden','true'); layer.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:200;overflow:hidden';
    for(var i=0;i<n;i++){
      var p=document.createElement('i'), a=Math.random()*Math.PI*2, d=80+Math.random()*160;
      p.style.cssText='position:absolute;left:'+x+'px;top:'+y+'px;width:'+(6+Math.random()*5)+'px;height:'+(4+Math.random()*6)+'px;background:'+COLORS[i%COLORS.length]+';border-radius:2px';
      p.animate([{transform:'translate(0,0) rotate(0)',opacity:1},{transform:'translate('+Math.cos(a)*d+'px,'+(Math.sin(a)*d-60)+'px) rotate('+Math.random()*360+'deg)',opacity:1,offset:.45},{transform:'translate('+Math.cos(a)*d*1.2+'px,'+(Math.sin(a)*d+220)+'px) rotate('+Math.random()*720+'deg)',opacity:0}],{duration:1300+Math.random()*500,easing:'cubic-bezier(.2,.7,.4,1)',fill:'forwards'});
      layer.appendChild(p);
    }
    document.body.appendChild(layer); setTimeout(function(){layer.remove()},2000);
  };
  function countUp(root){
    (root||document).querySelectorAll('[data-count]').forEach(function(el){
      var to=parseInt(el.dataset.count,10); if(isNaN(to)||el.dataset.counted) return; el.dataset.counted='1';
      if(still||to===0){el.textContent=to;return}
      var t0=performance.now(); el.textContent='0';
      (function tick(t){var k=Math.min(1,(t-t0)/700);el.textContent=Math.round(to*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(tick)})(t0);
    });
  }
  countUp();
  var lastDone=null;
  document.body.addEventListener('htmx:afterSwap',function(e){
    countUp(e.target);
    var st=document.getElementById('todo-state'); if(!st||e.target.id!=='todo-list') return;
    var total=+st.dataset.total, done=+st.dataset.done;
    if(lastDone!==null&&lastDone<total&&total>0&&done===total) window.pqConfetti();   // the last one just got ticked
    lastDone=done;
  });
})();
