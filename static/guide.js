let guideEls = {};
let totalSteps = 0;

document.addEventListener('DOMContentLoaded', () => {
  guideEls = {
    progressFill: document.getElementById('progress-fill'),
    stepCount: document.getElementById('step-count'),
    stageName: document.getElementById('stage-name'),
    moveNotation: document.getElementById('move-notation'),
    moveDescription: document.getElementById('move-description'),
    cubeDiagram: document.getElementById('cube-diagram'),
    moveView: document.getElementById('move-view'),
    solvedView: document.getElementById('solved-view'),
    nextBtn: document.getElementById('next-btn'),
    backBtn: document.getElementById('back-btn'),
    restartBtn: document.getElementById('restart-btn'),
  };
  guideEls.nextBtn.addEventListener('click', () => stepRequest('/api/step/next'));
  guideEls.backBtn.addEventListener('click', () => stepRequest('/api/step/back'));
  guideEls.restartBtn.addEventListener('click', restart);
});

window.initGuide = function (data) {
  totalSteps = data.total_steps;
  renderStep(data.step);
};

async function stepRequest(url) {
  const res = await fetch(url, { method: 'POST' });
  const data = await res.json();
  renderStep(data);
}

function renderStep(step) {
  if (!step || step.done) {
    guideEls.moveView.style.display = 'none';
    guideEls.solvedView.style.display = 'block';
    guideEls.progressFill.style.width = '100%';
    guideEls.stepCount.textContent = `${totalSteps}/${totalSteps} moves complete`;
    guideEls.stageName.textContent = '';
    return;
  }
  guideEls.moveView.style.display = 'block';
  guideEls.solvedView.style.display = 'none';

  const pct = totalSteps ? Math.round(((step.step_index - 1) / totalSteps) * 100) : 0;
  guideEls.progressFill.style.width = pct + '%';
  guideEls.stepCount.textContent = `Step ${step.step_index}/${step.total_steps}`;
  guideEls.stageName.textContent = step.stage.replace(/_/g, ' ');
  guideEls.moveNotation.textContent = step.notation;
  guideEls.moveDescription.textContent = step.description;
  guideEls.backBtn.disabled = step.step_index <= 1;
  renderCubeDiagram(guideEls.cubeDiagram, step.face, step.direction);
}

async function restart() {
  await fetch('/api/reset', { method: 'POST' });
  window.location.reload();
}
