/**
 * CTM Cabapuã — Scripts Globais
 */

document.addEventListener('DOMContentLoaded', function () {

    /* ─────────────────────────────────────────────
       1. Auto-hide alerts após 5 segundos
    ───────────────────────────────────────────── */
    document.querySelectorAll('.alert:not(.alert-permanent)').forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(10px)';
            setTimeout(function () { alert.remove(); }, 500);
        }, 5000);
    });

    /* ─────────────────────────────────────────────
       2. Confirmação de exclusão
    ───────────────────────────────────────────── */
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            var msg = el.getAttribute('data-confirm') || 'Tem certeza? Esta ação não pode ser desfeita.';
            if (!confirm(msg)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    // Compatibilidade com forms de excluir antigos
    document.querySelectorAll('form[action*="excluir"], form[action*="deletar"], form[action*="delete"]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm('Tem certeza que deseja excluir? Esta ação não pode ser desfeita.')) {
                e.preventDefault();
            }
        });
    });

    /* ─────────────────────────────────────────────
       3. Formata campos monetários (blur)
    ───────────────────────────────────────────── */
    document.querySelectorAll('input[data-currency], input[type="number"][step="0.01"]').forEach(function (input) {
        input.addEventListener('blur', function () {
            var value = parseFloat(this.value);
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });

    /* ─────────────────────────────────────────────
       4. Tooltip Bootstrap (se disponível)
    ───────────────────────────────────────────── */
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            new bootstrap.Tooltip(el);
        });
    }

    /* ─────────────────────────────────────────────
       5. Highlight da linha de tabela ao clicar
    ───────────────────────────────────────────── */
    document.querySelectorAll('.table-clickable tbody tr').forEach(function (row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function () {
            var link = row.querySelector('a[data-row-link]');
            if (link) window.location.href = link.href;
        });
    });

    /* ─────────────────────────────────────────────
       6. Spinner em botões de submit
    ───────────────────────────────────────────── */
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                var original = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Aguarde...';
                // Restaura caso o formulário falhe (ex: validação HTML5)
                setTimeout(function () {
                    btn.disabled = false;
                    btn.innerHTML = original;
                }, 8000);
            }
        });
    });

    /* ─────────────────────────────────────────────
       7. Search / filtro de tabela em tempo real
    ───────────────────────────────────────────── */
    var searchInput = document.getElementById('table-search');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var query = this.value.toLowerCase().trim();
            var rows = document.querySelectorAll('[data-searchable] tbody tr');
            var visible = 0;
            rows.forEach(function (row) {
                var text = row.textContent.toLowerCase();
                var match = text.includes(query);
                row.style.display = match ? '' : 'none';
                if (match) visible++;
            });

            var counter = document.getElementById('search-count');
            if (counter) counter.textContent = visible + ' resultado(s)';
        });
    }

    /* ─────────────────────────────────────────────
       8. Flash de sucesso com ícone (helper global)
         Uso: showToast('Mensagem', 'success')
    ───────────────────────────────────────────── */
    window.showToast = function (message, type) {
        type = type || 'info';
        var icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        var toast = document.createElement('div');
        toast.style.cssText = [
            'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9999',
            'background:rgba(30,27,58,0.95)', 'color:#f0f0f5',
            'border:1px solid rgba(255,255,255,0.15)', 'border-radius:12px',
            'padding:14px 20px', 'font-size:0.9rem', 'font-weight:500',
            'box-shadow:0 8px 30px rgba(0,0,0,0.4)',
            'backdrop-filter:blur(20px)',
            'transition:opacity 0.4s ease, transform 0.4s ease',
            'display:flex', 'align-items:center', 'gap:10px',
            'max-width:340px'
        ].join(';');
        toast.innerHTML = (icons[type] || '') + ' ' + message;
        document.body.appendChild(toast);

        setTimeout(function () {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            setTimeout(function () { toast.remove(); }, 400);
        }, 3500);
    };

});
