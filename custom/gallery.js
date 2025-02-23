document.addEventListener("DOMContentLoaded", function () {
  // Find every gallery container on the page
  const galleryContainers = document.querySelectorAll(
    ".custom-gallery-container"
  );

  galleryContainers.forEach((container) => {
    // Pull images from data-images
    const imagesJson = container.dataset.images;
    if (!imagesJson) return; // no data-images found, skip

    let images;
    try {
      images = JSON.parse(imagesJson);
    } catch (e) {
      console.error("Invalid JSON in data-images:", e);
      return;
    }

    // Create overlay elements
    const overlay = document.createElement("div");
    overlay.className = "gallery-overlay";

    const overlayContent = document.createElement("div");
    overlayContent.className = "gallery-overlay-content";

    const overlayImg = document.createElement("img");
    overlayImg.className = "gallery-image";

    const loadingIndicator = document.createElement("div");
    loadingIndicator.className = "gallery-loading";
    loadingIndicator.textContent = "Loading...";
    loadingIndicator.style.display = "none";

    const overlayCaption = document.createElement("div");
    overlayCaption.className = "gallery-caption";

    const prevBtn = document.createElement("button");
    prevBtn.className = "prev-btn gallery-btn";
    prevBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19 13H6.75L12 18.25l-.66.75l-6.5-6.5l6.5-6.5l.66.75L6.75 12H19z"/></svg>';
    prevBtn.setAttribute("aria-label", "Previous image");

    const nextBtn = document.createElement("button");
    nextBtn.className = "next-btn gallery-btn";
    nextBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M4 12h12.25L11 6.75l.66-.75l6.5 6.5l-6.5 6.5l-.66-.75L16.25 13H4z"/></svg>';
    nextBtn.setAttribute("aria-label", "Next image");

    const closeBtn = document.createElement("button");
    closeBtn.className = "close-btn";
    closeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12z"/></svg>';
    closeBtn.setAttribute("aria-label", "Close gallery");

    overlayContent.appendChild(closeBtn);
    overlayContent.appendChild(overlayImg);
    overlayContent.appendChild(loadingIndicator);
    overlayContent.appendChild(overlayCaption);
    overlayContent.appendChild(prevBtn);
    overlayContent.appendChild(nextBtn);
    overlay.appendChild(overlayContent);
    document.body.appendChild(overlay);

    // Initial image setup
    const mainImg = container.querySelector(".gallery-image");
    const mainCaption = container.querySelector(".gallery-caption");

    // Create and add the "Open Gallery" button
    const openBtn = document.createElement("button");
    openBtn.className = "open-gallery-btn";
    openBtn.innerHTML = '<i class="fas fa-expand-alt"></i> View Gallery';
    container.appendChild(openBtn);

    let currentIndex = 0;

    function showImage(index, target = "main") {
      // wrap-around logic
      if (index < 0) {
        currentIndex = images.length - 1;
      } else if (index >= images.length) {
        currentIndex = 0;
      } else {
        currentIndex = index;
      }

      const { url, caption } = images[currentIndex];
      const targetImg = target === "main" ? mainImg : overlayImg;
      const targetCaption = target === "main" ? mainCaption : overlayCaption;
      
      if (target === "overlay") {
        loadingIndicator.style.display = "block";
      }

      // Create a new image object to preload
      const tempImg = new Image();
      tempImg.onload = () => {
        targetImg.src = url;
        targetImg.alt = caption || "Gallery image";
        targetCaption.textContent = caption || "";
        if (target === "overlay") {
          loadingIndicator.style.display = "none";
        }
      };
      tempImg.src = url;
    }

    // Initialize main image
    showImage(0, "main");

    // Event Listeners
    openBtn.addEventListener("click", () => {
      overlay.classList.add("active");
      showImage(currentIndex, "overlay");
    });

    closeBtn.addEventListener("click", () => {
      overlay.classList.remove("active");
    });

    prevBtn.addEventListener("click", () =>
      showImage(currentIndex - 1, "overlay")
    );
    nextBtn.addEventListener("click", () =>
      showImage(currentIndex + 1, "overlay")
    );

    // Close on escape key and handle arrow keys
    document.addEventListener("keydown", (e) => {
      if (!overlay.classList.contains("active")) return;
      
      switch (e.key) {
        case "Escape":
          overlay.classList.remove("active");
          break;
        case "ArrowLeft":
          showImage(currentIndex - 1, "overlay");
          break;
        case "ArrowRight":
          showImage(currentIndex + 1, "overlay");
          break;
      }
    });

    // Close on click outside
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("active");
      }
    });
  });
});
