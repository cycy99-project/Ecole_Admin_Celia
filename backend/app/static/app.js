(function () {
    const dialog = document.getElementById('reserveDialog');
    const form = document.getElementById('reserveForm');
    const dlgDay = document.getElementById('dlgDay');
    const dlgTime = document.getElementById('dlgTime');
    const cancelBtn = document.getElementById('dlgCancel');

    if (!dialog || !form) return;

    document.querySelectorAll('.slot-reserve-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const slotId = btn.dataset.slotId;
            const slotTime = btn.dataset.slotTime;
            const slotDay = btn.dataset.slotDay;
            form.action = btn.dataset.action || ('/reserver/' + slotId);
            if (dlgTime) dlgTime.textContent = slotTime;
            if (dlgDay) dlgDay.textContent = slotDay;
            const firstInput = form.querySelector('input[name="child_first_name"]');
            if (firstInput) firstInput.value = '';
            const lastInput = form.querySelector('input[name="child_last_name"]');
            if (lastInput) lastInput.value = '';
            if (typeof dialog.showModal === 'function') {
                dialog.showModal();
                setTimeout(function () { firstInput && firstInput.focus(); }, 50);
            } else {
                form.submit();
            }
        });
    });

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
            dialog.close();
        });
    }

    dialog.addEventListener('click', function (e) {
        if (e.target === dialog) {
            dialog.close();
        }
    });
})();
