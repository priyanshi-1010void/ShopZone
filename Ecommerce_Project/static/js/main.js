/**
 * ShopZone Interactive JavaScript
 * Modern UI enhancements inspired by Amazon, Flipkart & Meesho
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Quantity Stepper in Product View & Cart
    initQuantitySteppers();

    // 2. Alert Dismissals
    initAlertDismiss();

    // 3. Price Filter Slider
    initPriceSlider();
});

function initQuantitySteppers() {
    document.querySelectorAll('.qty-stepper').forEach(stepper => {
        const minusBtn = stepper.querySelector('.qty-minus');
        const plusBtn = stepper.querySelector('.qty-plus');
        const input = stepper.querySelector('.qty-input');

        if (minusBtn && plusBtn && input) {
            const min = parseInt(input.getAttribute('min')) || 1;
            const max = parseInt(input.getAttribute('max')) || 99;

            minusBtn.addEventListener('click', (e) => {
                e.preventDefault();
                let val = parseInt(input.value) || 1;
                if (val > min) {
                    input.value = val - 1;
                    triggerChange(input);
                }
            });

            plusBtn.addEventListener('click', (e) => {
                e.preventDefault();
                let val = parseInt(input.value) || 1;
                if (val < max) {
                    input.value = val + 1;
                    triggerChange(input);
                }
            });
        }
    });
}

function triggerChange(element) {
    const event = new Event('change', { bubbles: true });
    element.dispatchEvent(event);
    // If inside auto-submit form
    const form = element.closest('form');
    if (form && form.classList.contains('auto-submit-form')) {
        form.submit();
    }
}

function initAlertDismiss() {
    document.querySelectorAll('.alert-close').forEach(btn => {
        btn.addEventListener('click', () => {
            const alert = btn.closest('.alert');
            if (alert) {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 250);
            }
        });
    });
}

function initPriceSlider() {
    const slider = document.getElementById('priceRangeSlider');
    const priceDisplay = document.getElementById('priceRangeDisplay');
    if (slider && priceDisplay) {
        slider.addEventListener('input', (e) => {
            priceDisplay.textContent = '₹' + parseInt(e.target.value).toLocaleString('en-IN');
        });
    }
}

// Quick apply coupon code helper
function applyCouponCode(code) {
    const couponInput = document.getElementById('couponCodeInput');
    if (couponInput) {
        couponInput.value = code;
        const form = couponInput.closest('form');
        if (form) form.submit();
    }
}

// Print Invoice helper for Order Confirmation & Tracking
function printInvoice() {
    window.print();
}
