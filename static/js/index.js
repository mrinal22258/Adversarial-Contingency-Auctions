/**
 * Adversarial Contingency Auctions (ACA) Project Page JavaScript
 * Handles navigation burgers, bibtex copy actions, and interactive carousels.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Navbar Burger Toggle
  const navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);
  if (navbarBurgers.length > 0) {
    navbarBurgers.forEach(el => {
      el.addEventListener('click', () => {
        const target = el.dataset.target;
        const $target = document.getElementById(target);
        el.classList.toggle('is-active');
        if ($target) {
          $target.classList.toggle('is-active');
        }
      });
    });
  }

  // 2. BibTeX Copy to Clipboard Button
  const copyBtn = document.getElementById('copy-bibtex-btn');
  const bibtexCode = document.getElementById('bibtex-code');
  if (copyBtn && bibtexCode) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(bibtexCode.innerText.trim());
        const originalHtml = copyBtn.innerHTML;
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.innerHTML = originalHtml;
        }, 2500);
      } catch (err) {
        console.error('Failed to copy BibTeX: ', err);
      }
    });
  }

  // 3. Bulma Carousel Initialization (if attached)
  if (typeof bulmaCarousel !== 'undefined') {
    bulmaCarousel.attach('.carousel, .results-carousel', {
      slidesToScroll: 1,
      slidesToShow: 3,
      loop: true,
      infinite: true,
      autoplay: true,
      autoplaySpeed: 4000,
      breakpoints: [
        { changePoint: 480, slidesToShow: 1, slidesToScroll: 1 },
        { changePoint: 768, slidesToShow: 2, slidesToScroll: 1 },
        { changePoint: 1024, slidesToShow: 3, slidesToScroll: 1 }
      ]
    });
  }
});
