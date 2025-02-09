document.addEventListener('DOMContentLoaded', function() {
  // -----------------------------------------
  // Mobile Menu Toggle
  // -----------------------------------------
  const menuToggle = document.getElementById('menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (menuToggle) {
    menuToggle.addEventListener('click', function() {
      navLinks.classList.toggle('active');
    });
  }
  
  // -----------------------------------------
  // Back-to-Top Button Functionality
  // -----------------------------------------
  const backToTop = document.getElementById('back-to-top');
  window.addEventListener('scroll', function() {
    if (window.pageYOffset > 300) {
      backToTop.style.display = 'block';
    } else {
      backToTop.style.display = 'none';
    }
  });
  backToTop.addEventListener('click', function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  
  // -----------------------------------------
  // Toast Auto-Dismiss Functionality
  // -----------------------------------------
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(function(toast) {
    setTimeout(function() {
      toast.style.opacity = '0';
      setTimeout(function() {
        toast.remove();
      }, 500);
    }, 4000);
  });
  
  // -----------------------------------------
  // Dark Mode Toggle with LocalStorage Persistence
  // -----------------------------------------
  const toggleDarkMode = document.getElementById('toggleDarkMode');
  if (toggleDarkMode) {
    toggleDarkMode.addEventListener('click', function() {
      document.body.classList.toggle('dark-mode');
      if (document.body.classList.contains('dark-mode')) {
        localStorage.setItem('theme', 'dark');
      } else {
        localStorage.setItem('theme', 'light');
      }
    });
    if (localStorage.getItem('theme') === 'dark') {
      document.body.classList.add('dark-mode');
    }
  }
  
  // -----------------------------------------
  // Transaction Details Modal Feature
  // -----------------------------------------
  // Ensure the modal elements exist in your base.html:
  // <div id="transactionModal" class="modal">
  //   <div class="modal-content">
  //     <span class="close-modal">&times;</span>
  //     <h2>Transaction Details</h2>
  //     <div id="modalBody"></div>
  //   </div>
  // </div>
  
  const modal = document.getElementById('transactionModal');
  const modalBody = document.getElementById('modalBody');
  const closeModal = document.querySelector('.close-modal');
  
  // Attach click event to all "View Details" links
  document.querySelectorAll('.view-details').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const txId = this.getAttribute('data-tx-id');
      fetch(`/transaction_details/${txId}`)
        .then(response => response.json())
        .then(data => {
          modalBody.innerHTML = `
            <p><strong>Date:</strong> ${data.date}</p>
            <p><strong>Type:</strong> ${data.type}</p>
            <p><strong>Category:</strong> ${data.category}</p>
            <p><strong>Amount:</strong> $${data.amount}</p>
            <p><strong>Description:</strong> ${data.description}</p>
            <p><strong>Recurring:</strong> ${data.recurring}</p>
            ${data.receipt ? `<p><strong>Receipt:</strong> <a href="/static/uploads/${data.receipt}" target="_blank">View Image</a></p>` : ''}
          `;
          modal.style.display = 'block';
        })
        .catch(err => console.error(err));
    });
  });
  
  // Close modal when clicking the close button
  if (closeModal) {
    closeModal.addEventListener('click', function() {
      modal.style.display = 'none';
    });
  }
  
  // Close modal when clicking outside the modal content
  window.addEventListener('click', function(e) {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
});
