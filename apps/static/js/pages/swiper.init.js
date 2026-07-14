/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Swiper Js
*/

const swiper = new Swiper('.testi-swiper', {
    centeredSlides: true,
    spaceBetween: 24,
    loop: true,
    autoplay: {
      delay: 3000,
      disableOnInteraction: false,
    },
    navigation: {
        nextEl: ".testi-button-next",
        prevEl: ".testi-button-prev",
      },
    breakpoints: {
      0: {
        slidesPerView: 1,
      },
      768: {
        slidesPerView: 2,
      },
      991: {
        slidesPerView: 2.5,
      },
      1024: {
        slidesPerView: 3,
      },
    }
});