import React from 'react';

// --- ICONS (included for self-containment) ---

const TwitterIcon = (props: React.SVGProps<SVGSVGElement>) => (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"></path>
    </svg>
);

const LinkedinIcon = (props: React.SVGProps<SVGSVGElement>) => (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path>
        <rect x="2" y="9" width="4" height="12"></rect>
        <circle cx="4" cy="4" r="2"></circle>
    </svg>
);

const GithubIcon = (props: React.SVGProps<SVGSVGElement>) => (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
    </svg>
);

// --- FOOTER COMPONENT ---

const Footer = () => (
  <footer className="glassy-card border-t border-white/10 text-white pt-16 pb-8">
    <div className="container mx-auto px-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
        
        {/* About Section */}
        <div className="col-span-1 md:col-span-2">
          <h3 className="text-2xl font-bold text-white mb-2">
            Cogni<span className="text-[#8A5EFF]">Claim</span>
          </h3>
          <p className="text-[#F0F0F0] max-w-md">
            Revolutionizing insurance claims with AI to empower agents and provide unparalleled analytical insights.
          </p>
        </div>

        {/* Quick Links */}
        <div>
          <h4 className="font-semibold text-white mb-4">Quick Links</h4>
          <ul className="space-y-2">
            <li><a href="#features" className="text-[#F0F0F0] hover:text-[#A685FF]">Features</a></li>
            <li><a href="#about" className="text-[#F0F0F0] hover:text-[#A685FF]">About Us</a></li>
            <li><a href="#contact" className="text-[#F0F0F0] hover:text-[#A685FF]">Contact</a></li>
          </ul>
        </div>

        {/* Legal */}
        <div>
          <h4 className="font-semibold text-white mb-4">Legal</h4>
          <ul className="space-y-2">
            <li><a href="#" className="text-[#F0F0F0] hover:text-[#A685FF]">Privacy Policy</a></li>
            <li><a href="#" className="text-[#F0F0F0] hover:text-[#A685FF]">Terms of Service</a></li>
          </ul>
        </div>
        
      </div>

      <div className="border-t border-[#2A2C3A] pt-8 flex flex-col sm:flex-row justify-between items-center">
        <p className="text-sm text-[#F0F0F0]">&copy; {new Date().getFullYear()} CogniClaim. All rights reserved.</p>
        <div className="flex space-x-4 mt-4 sm:mt-0">
          <a href="#" className="text-[#F0F0F0] hover:text-[#A685FF]"><TwitterIcon className="w-6 h-6" /></a>
          <a href="#" className="text-[#F0F0F0] hover:text-[#A685FF]"><LinkedinIcon className="w-6 h-6" /></a>
          <a href="#" className="text-[#F0F0F0] hover:text-[#A685FF]"><GithubIcon className="w-6 h-6" /></a>
        </div>
      </div>
    </div>
  </footer>
);

export default Footer;

